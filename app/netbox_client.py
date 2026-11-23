import os
import requests

NETBOX_URL = os.getenv("NETBOX_URL")
NETBOX_TOKEN = os.getenv("NETBOX_TOKEN")

netbox = requests.Session()
netbox.headers.update({
    "Authorization": f"Token {NETBOX_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
})

N = f"{NETBOX_URL}/api/virtualization"

def get_cluster_id():
    r = netbox.get(f"{N}/clusters/", params={"name": "docker-local"}, timeout=10)
    r.raise_for_status()
    return r.json()["results"][0]["id"]

def create_vm(nom):
    id_cluster = get_cluster_id()

    r = netbox.post(
        f"{N}/virtual-machines/",
        json={
            "name": nom,
            "cluster": id_cluster,
            "status": "active"
        },
        timeout=10
    )

    r.raise_for_status()

def update_vm_status(nom, status):
    r = netbox.get(
        f"{N}/virtual-machines/",
        params={"name": nom},
        timeout=10
    )
    r.raise_for_status()

    results = r.json()["results"]

    if not results:
        return

    vm_id = results[0]["id"]

    r = netbox.patch(
        f"{N}/virtual-machines/{vm_id}/",
        json={"status": status},
        timeout=10
    )

    r.raise_for_status()

def delete_vm(nom):
    r = netbox.get(
        f"{N}/virtual-machines/",
        params={"name": nom},
        timeout=10
    )
    r.raise_for_status()

    results = r.json()["results"]

    if not results:
        return

    vm_id = results[0]["id"]

    r = netbox.delete(
        f"{N}/virtual-machines/{vm_id}/",
        timeout=10
    )

    r.raise_for_status()