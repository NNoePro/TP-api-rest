import os
import sys
import json
from datetime import datetime, timezone

import requests


# Configuration issue de l'environnement
DOCKER = os.environ.get("DOCKER_API_URL", "http://127.0.0.1:2375").rstrip("/")
NETBOX = os.environ.get("NETBOX_URL", "http://127.0.0.1:8080").rstrip("/")
JETON = os.environ["NETBOX_TOKEN"]

TIMEOUT = 10


def creer_session():
    """Crée une session HTTP réutilisable."""
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    return session


def recuperer_conteneurs(session):
    """Récupère tous les conteneurs Docker."""
    url = f"{DOCKER}/containers/json?all=true"

    response = session.get(url, timeout=TIMEOUT)
    response.raise_for_status()

    return response.json()


def recuperer_statistiques(session, container_id):
    """Récupère les statistiques d'un conteneur."""
    url = f"{DOCKER}/containers/{container_id}/stats?stream=false"

    response = session.get(url, timeout=TIMEOUT)
    response.raise_for_status()

    return response.json()


def calculer_cpu(stats):
    """Calcule le pourcentage CPU à partir des compteurs Docker."""
    cpu = stats["cpu_stats"]
    avant = stats.get("precpu_stats", {})

    delta_cpu = (
        cpu["cpu_usage"]["total_usage"]
        - avant.get("cpu_usage", {}).get("total_usage", 0)
    )

    delta_systeme = (
        cpu.get("system_cpu_usage", 0)
        - avant.get("system_cpu_usage", 0)
    )

    nombre_cpu = cpu.get("online_cpus", 1)

    if delta_systeme <= 0 or delta_cpu < 0:
        return 0.0

    pourcentage = delta_cpu / delta_systeme * nombre_cpu * 100
    return round(pourcentage, 2)


def calculer_memoire(stats):
    """Convertit la mémoire utilisée en Mio."""
    octets = stats["memory_stats"]["usage"]
    return round(octets / 1024 / 1024, 2)


def construire_inventaire_docker(session):
    """Construit la partie Docker de l'inventaire."""
    conteneurs = recuperer_conteneurs(session)
    releves = []

    for conteneur in conteneurs:
        nom = conteneur["Names"][0]
        image = conteneur["Image"]
        etat = conteneur["State"]

        releve = {
            "id": conteneur["Id"],
            "nom": nom,
            "image": image,
            "etat": etat,
            "cpu_percent": None,
            "memoire_mio": None,
        }

        if etat == "running":
            try:
                stats = recuperer_statistiques(session, conteneur["Id"])
                releve["cpu_percent"] = calculer_cpu(stats)
                releve["memoire_mio"] = calculer_memoire(stats)

            except (
                requests.exceptions.RequestException,
                KeyError,
                TypeError,
                ValueError,
            ) as erreur:
                print(
                    f"Attention : statistiques indisponibles pour {nom} : {erreur}",
                    file=sys.stderr,
                )

        releves.append(releve)

    return releves


def construire_session_netbox():
    """Crée une session authentifiée pour NetBox."""
    session = creer_session()
    session.headers.update({"Authorization": f"Bearer {JETON}"})
    return session


def recuperer_statut_netbox(session):
    """Récupère le statut et la version de NetBox."""
    url = f"{NETBOX}/api/status/"

    response = session.get(url, timeout=TIMEOUT)
    response.raise_for_status()

    donnees = response.json()

    return {
        "version": donnees.get("netbox-version"),
        "statut": donnees,
    }


def compter_types_objets(session):
    """Compte tous les types d'objets en suivant la pagination."""
    url = f"{NETBOX}/api/core/object-types/?limit=50"
    total = 0

    while url is not None:
        response = session.get(url, timeout=TIMEOUT)
        response.raise_for_status()

        page = response.json()
        total += len(page.get("results", []))

        url = page.get("next")

    return total


def construire_inventaire_netbox(session):
    """Construit la partie NetBox de l'inventaire."""
    statut = recuperer_statut_netbox(session)
    nombre_types = compter_types_objets(session)

    return {
        "version": statut["version"],
        "nombre_types_objets": nombre_types,
    }


def enregistrer_inventaire(inventaire):
    """Enregistre l'inventaire dans un fichier JSON."""
    with open("inventaire.json", "w", encoding="utf-8") as fichier:
        json.dump(
            inventaire,
            fichier,
            indent=4,
            ensure_ascii=False,
        )


def afficher_resume(inventaire):
    """Affiche un résumé lisible de l'inventaire."""
    conteneurs = inventaire["docker"]["conteneurs"]

    print("\n========== RÉSUMÉ DE L'INVENTAIRE ==========")
    print(f"Date du relevé : {inventaire['date_releve']}")
    print(f"Nombre de conteneurs : {len(conteneurs)}")

    for conteneur in conteneurs:
        print(
            f"- {conteneur['nom']} | "
            f"Image : {conteneur['image']} | "
            f"État : {conteneur['etat']} | "
            f"CPU : {conteneur['cpu_percent']} % | "
            f"Mémoire : {conteneur['memoire_mio']} Mio"
        )

    netbox = inventaire["netbox"]
    print(f"\nVersion NetBox : {netbox['version']}")
    print(f"Types d'objets NetBox : {netbox['nombre_types_objets']}")
    print("Fichier créé : inventaire.json")


def main():
    """Point d'entrée du programme."""
    session_docker = creer_session()

    try:
        # Docker est indispensable à la création de l'inventaire.
        conteneurs = construire_inventaire_docker(session_docker)

    except requests.exceptions.RequestException as erreur:
        sys.exit(f"Erreur : impossible de contacter l'API Docker : {erreur}")

    session_netbox = construire_session_netbox()

    try:
        netbox = construire_inventaire_netbox(session_netbox)

    except requests.exceptions.RequestException as erreur:
        sys.exit(f"Erreur : impossible de contacter l'API NetBox : {erreur}")

    except (KeyError, TypeError, ValueError) as erreur:
        sys.exit(f"Erreur : réponse NetBox invalide : {erreur}")

    inventaire = {
        "date_releve": datetime.now(timezone.utc).isoformat(),
        "docker": {
            "conteneurs": conteneurs,
        },
        "netbox": netbox,
    }

    try:
        enregistrer_inventaire(inventaire)

    except OSError as erreur:
        sys.exit(f"Erreur : impossible d'écrire inventaire.json : {erreur}")

    afficher_resume(inventaire)


if __name__ == "__main__":
    main()