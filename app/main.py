from fastapi import FastAPI, HTTPException, Response, Depends
from pydantic import BaseModel, Field
from app.securite import require_read, require_admin
from app.netbox_client import create_vm, update_vm_status, delete_vm
import requests
import os

app = FastAPI()


# Modèle pour la création d'un conteneur
class ContainerCreate(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{1,30}$")
    image: str = Field(pattern=r"^(nginx:alpine|redis:alpine|httpd:alpine)$")


# GET /health
@app.get("/health")
def health():
    return {"status": "ok"}


# GET /containers
@app.get("/containers")
def get_containers(role=Depends(require_read)):
    docker_api_url = os.getenv("DOCKER_API_URL")
    url = f"{docker_api_url}/containers/json?all=true"

    response = requests.get(url, timeout=10)
    response.raise_for_status()

    conteneurs = response.json()
    resultats = []

    for conteneur in conteneurs:
        labels = conteneur.get("Labels") or {}

        if labels.get("adminapi.managed") == "true":
            resultats.append({
                "id": conteneur.get("Id"),
                "name": conteneur.get("Names", ["/"])[0].lstrip("/"),
                "image": conteneur.get("Image"),
                "state": conteneur.get("State"),
            })

    return resultats


# GET /containers/{id}
@app.get("/containers/{id}")
def get_container(id: str, role=Depends(require_read)):
    for conteneur in get_containers():
        if conteneur["id"] == id:
            return conteneur

    raise HTTPException(status_code=404, detail="Conteneur introuvable")


# POST /containers
@app.post("/containers", status_code=201)
def create_container(data: ContainerCreate, role=Depends(require_admin)):
    docker_api_url = os.getenv("DOCKER_API_URL")

    # Création du conteneur
    url = f"{docker_api_url}/containers/create"

    corps = {
        "Image": data.image,
        "Labels": {
            "adminapi.managed": "true"
        }
    }

    response = requests.post(
        url,
        params={"name": data.name},
        json=corps,
        timeout=10
    )

    # Le nom est déjà utilisé
    if response.status_code == 409:
        raise HTTPException(status_code=409, detail="Nom déjà utilisé")

    response.raise_for_status()

    container_id = response.json()["Id"]

    # Démarrage du conteneur
    start_url = f"{docker_api_url}/containers/{container_id}/start"

    start_response = requests.post(start_url, timeout=10)
    start_response.raise_for_status()

    # Relecture de l'état réel du conteneur
    container_url = f"{docker_api_url}/containers/{container_id}/json"

    container_response = requests.get(container_url, timeout=10)
    container_response.raise_for_status()

    container = container_response.json()

    # Création de la VM dans NetBox
    create_vm(data.name)

    return {
        "id": container.get("Id"),
        "name": container.get("Name", "").lstrip("/"),
        "image": data.image,
        "state": container.get("State", {}).get("Status"),
    }


# POST /containers/{id}/stop
@app.post("/containers/{id}/stop")
def stop_container(id: str, role=Depends(require_admin)):
    try:
        container_info = get_container(id)

        if container_info["state"] == "exited":
            raise HTTPException(
                status_code=409,
                detail="Conteneur déjà arrêté",
            )

        docker_api_url = os.getenv("DOCKER_API_URL")
        if not docker_api_url:
            raise HTTPException(
                status_code=500,
                detail="DOCKER_API_URL non configurée",
            )

        # Arrêt du conteneur Docker
        stop_url = f"{docker_api_url}/containers/{id}/stop"
        response = requests.post(
            stop_url,
            params={"t": 2},
            timeout=30,
        )

        if response.status_code == 304:
            raise HTTPException(status_code=409, detail="Conteneur déjà arrêté")

        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail="Conteneur introuvable ou non géré",
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Erreur de l'API Docker ({response.status_code})",
            )

        # Relecture de l'état réel
        inspect_url = f"{docker_api_url}/containers/{id}/json"
        inspect_response = requests.get(inspect_url, timeout=10)
        inspect_response.raise_for_status()

        container = inspect_response.json()
        nom = container.get("Name", "").lstrip("/")

        # Synchronisation NetBox : VM offline
        update_vm_status(nom, "offline")

    except HTTPException:
        raise
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail="Impossible de communiquer avec Docker ou NetBox",
        ) from exc

    return {
        "id": container.get("Id"),
        "name": nom,
        "image": container.get("Config", {}).get("Image"),
        "state": container.get("State", {}).get("Status"),
    }


# POST /containers/{id}/start
@app.post("/containers/{id}/start")
def start_container(id: str, role=Depends(require_admin)):
    try:
        container_info = get_container(id)

        if container_info["state"] == "running":
            raise HTTPException(
                status_code=409,
                detail="Conteneur déjà démarré",
            )

        docker_api_url = os.getenv("DOCKER_API_URL")
        if not docker_api_url:
            raise HTTPException(
                status_code=500,
                detail="DOCKER_API_URL non configurée",
            )

        # Démarrage du conteneur Docker
        start_url = f"{docker_api_url}/containers/{id}/start"
        response = requests.post(start_url, timeout=30)

        if response.status_code == 304:
            raise HTTPException(status_code=409, detail="Conteneur déjà démarré")

        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail="Conteneur introuvable ou non géré",
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Erreur de l'API Docker ({response.status_code})",
            )

        # Relecture de l'état réel
        inspect_url = f"{docker_api_url}/containers/{id}/json"
        inspect_response = requests.get(inspect_url, timeout=10)
        inspect_response.raise_for_status()

        container = inspect_response.json()
        nom = container.get("Name", "").lstrip("/")

        # Synchronisation NetBox : VM active
        update_vm_status(nom, "active")

    except HTTPException:
        raise
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail="Impossible de communiquer avec Docker ou NetBox",
        ) from exc

    return {
        "id": container.get("Id"),
        "name": nom,
        "image": container.get("Config", {}).get("Image"),
        "state": container.get("State", {}).get("Status"),
    }


# DELETE /containers/{id}
@app.delete("/containers/{id}", status_code=204, response_class=Response)
def delete_container(id: str, role=Depends(require_admin)):
    try:
        # Vérifier le conteneur et récupérer son nom
        container_info = get_container(id)
        nom = container_info["name"]

        docker_api_url = os.getenv("DOCKER_API_URL")
        if not docker_api_url:
            raise HTTPException(
                status_code=500,
                detail="DOCKER_API_URL non configurée",
            )

        url = f"{docker_api_url}/containers/{id}"

        # Suppression du conteneur Docker
        response = requests.delete(
            url,
            params={"force": "true"},
            timeout=30,
        )

        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail="Conteneur introuvable ou non géré",
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Erreur de l'API Docker ({response.status_code})",
            )

        # Suppression de la VM dans NetBox
        delete_vm(nom)

    except HTTPException:
        raise
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail="Impossible de communiquer avec Docker ou NetBox",
        ) from exc

    return Response(status_code=204)
