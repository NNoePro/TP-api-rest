
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
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
def get_containers():
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
def get_container(id: str):
    for conteneur in get_containers():
        if conteneur["id"] == id:
            return conteneur

    raise HTTPException(status_code=404, detail="Conteneur introuvable")


# POST /containers
@app.post("/containers", status_code=201)
def create_container(data: ContainerCreate):
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

    return {
        "id": container.get("Id"),
        "name": container.get("Name", "").lstrip("/"),
        "image": data.image,
        "state": container.get("State", {}).get("Status"),
    }

@app.post("/containers/{id}/stop")
def stop_container(id: str):
    try:
        # Cette fonction vérifie que le conteneur existe et porte
        # le label adminapi.managed=true.
        container = get_container(id)

        if container["state"] == "exited":
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

        # Demander l'arrêt et laisser 2 secondes au processus pour s'arrêter.
        stop_url = f"{docker_api_url}/containers/{id}/stop"
        response = requests.post(
            stop_url,
            params={"t": 2},
            timeout=30,
        )

        if response.status_code == 304:
            raise HTTPException(
                status_code=409,
                detail="Conteneur déjà arrêté",
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

        # Relire le conteneur après l'arrêt pour obtenir son état réel.
        inspect_url = f"{docker_api_url}/containers/{id}/json"
        inspect_response = requests.get(inspect_url, timeout=10)

        if inspect_response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail="Conteneur introuvable ou non géré",
            )

        if inspect_response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Erreur de l'API Docker ({inspect_response.status_code})",
            )

        container = inspect_response.json()

    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail="Impossible de communiquer avec l'API Docker",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Réponse JSON invalide de l'API Docker",
        ) from exc

    return {
        "id": container.get("Id"),
        "name": container.get("Name", "").lstrip("/"),
        "image": container.get("Config", {}).get("Image"),
        "state": container.get("State", {}).get("Status"),
    }