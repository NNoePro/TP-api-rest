from fastapi import FastAPI, HTTPException
import requests
import os

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/containers")
def get_containers():
    docker_api_url = os.getenv("DOCKER_API_URL")
    url = f"{docker_api_url}/containers/json?all=true"
    reponse = requests.get(url)
    reponse.raise_for_status()
    conteneurs = reponse.json()

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

@app.get("/containers/{id}")
def get_container(id: str):
    for conteneur in get_containers():
        if conteneur["id"] == id:
            return conteneur
    raise HTTPException(status_code=404, detail="Conteneur introuvable")