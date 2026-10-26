TP1 — Exploration des API Docker et NetBox

1. Objectifs du TP

Ce TP a pour objectif de découvrir les API REST de Docker et de NetBox, d’effectuer des requêtes HTTP manuelles et d’analyser les réponses obtenues.

Les manipulations réalisées permettent notamment de :

* Explorer l’API Docker à l’aide de requêtes HTTP.
* Créer et identifier des conteneurs Docker.
* Filtrer les conteneurs à l’aide de labels.
* Observer les codes HTTP associés aux différentes opérations.
* Authentifier des requêtes auprès de l’API NetBox.
* Créer un type de cluster et un cluster dans NetBox.
* Vérifier que les objets créés sont accessibles via l’API.

2. Environnement de travail

Composant	Adresse ou configuration
Système de travail	macOS sur Apple Silicon
API Docker	http://127.0.0.1:2375
Interface NetBox	http://127.0.0.1:8080
API NetBox	http://127.0.0.1:8080/api/
Image utilisée	nginx:alpine
Type de cluster créé	Docker
Cluster créé	docker-local

Les commandes ont été exécutées dans un terminal depuis le répertoire du projet TP-api-rest.

3. Exploration de l’API Docker

3.1. Création des conteneurs

Deux conteneurs Nginx ont été créés pour distinguer les conteneurs gérés par l’application des conteneurs non gérés.

Création de web1 avec le label adminapi.managed=true :

docker run -d --name web1 --label adminapi.managed=true nginx:alpine

Création de intrus sans le label de gestion :

docker run -d --name intrus nginx:alpine

Le conteneur web1 représente un conteneur géré par l’application. Le conteneur intrus sert de contre-exemple pour les tests de filtrage.

3.2. Vérification des labels

La commande suivante permet de consulter le nom et les labels des deux conteneurs :

docker inspect --format '{{.Name}} {{json .Config.Labels}}' web1 intrus

Le résultat a confirmé que web1 possède le label adminapi.managed=true, contrairement à intrus.

3.3. Vérification de l’accessibilité de l’API Docker

La commande suivante permet de consulter la version du moteur Docker :

curl -i http://127.0.0.1:2375/version

Résultat observé : HTTP/1.1 200 OK.

La réponse contient notamment la version du moteur Docker (29.7.2) et la version de son API (1.55).

Ce test confirme que l’API Docker est accessible depuis l’environnement de travail.

3.4. Liste de tous les conteneurs

Pour afficher tous les conteneurs, y compris ceux qui sont arrêtés, la commande suivante a été utilisée :

curl -i 'http://127.0.0.1:2375/containers/json?all=true'

Résultat observé : HTTP/1.1 200 OK.

La réponse JSON contient les informations des conteneurs présents sur l’hôte Docker, notamment web1, intrus et les conteneurs associés à NetBox.

Le paramètre all=true permet également d’inclure les conteneurs qui ne sont pas en cours d’exécution.

3.5. Filtrage des conteneurs par label

Pour ne récupérer que les conteneurs possédant le label adminapi.managed=true, la commande suivante a été exécutée :

curl -i 'http://127.0.0.1:2375/containers/json?filters=%7B%22label%22%3A%5B%22adminapi.managed%3Dtrue%22%5D%7D'

Le paramètre filters contient un objet JSON encodé dans l’URL. Il demande à Docker de filtrer les conteneurs en fonction du label spécifié.

Résultat observé : HTTP/1.1 200 OK.

Seul web1 apparaît dans la réponse. Le conteneur intrus est exclu puisqu’il ne possède pas le label demandé.

Ce mécanisme permet de distinguer les conteneurs administrés par l’application des autres conteneurs présents sur l’hôte.

3.6. Consultation des informations d’un conteneur

Pour récupérer les informations détaillées de web1, la commande suivante a été exécutée :

curl -i http://127.0.0.1:2375/containers/web1/json

Résultat observé : HTTP/1.1 200 OK.

La réponse JSON contient notamment :

* Le nom du conteneur : /web1.
* L’image utilisée : nginx:alpine.
* L’état du conteneur : running.
* Les labels associés.
* Les informations de configuration et de réseau.

Cette requête permet de consulter l’état et la configuration d’un conteneur précis.

3.7. Arrêt d’un conteneur en cours d’exécution

La commande suivante a été utilisée pour arrêter web1 :

curl -i -X POST http://127.0.0.1:2375/containers/web1/stop

Résultat observé : HTTP/1.1 204 No Content.

Le code 204 indique que l’opération a réussi et que la réponse ne contient pas de corps.

Le conteneur a été arrêté.

3.8. Tentative d’arrêt d’un conteneur déjà arrêté

La même commande a été exécutée une seconde fois :

curl -i -X POST http://127.0.0.1:2375/containers/web1/stop

Résultat observé : HTTP/1.1 304 Not Modified.

Dans cette installation, Docker renvoie le code 304 lorsque le conteneur est déjà arrêté et que son état ne change pas.

Ce résultat illustre l’importance de tester les opérations dans plusieurs états possibles.

3.9. Tentative d’arrêt d’un conteneur inexistant

Pour tester le comportement de l’API lorsqu’un conteneur n’existe pas, la commande suivante a été exécutée :

curl -i -X POST http://127.0.0.1:2375/containers/inexistant/stop

Résultat observé : HTTP/1.1 404 Not Found.

La réponse JSON contient le message :

{
  "message": "No such container: inexistant"
}

Le code 404 indique que Docker ne trouve aucun conteneur correspondant au nom demandé.

3.10. Synthèse des tests Docker

Opération	Méthode HTTP	Code observé	Interprétation
Consulter la version Docker	GET	200 OK	L’API est accessible.
Lister tous les conteneurs	GET	200 OK	La liste est renvoyée.
Filtrer par label	GET	200 OK	Seul web1 correspond au filtre.
Consulter les détails de web1	GET	200 OK	Les informations sont renvoyées.
Arrêter web1 en fonctionnement	POST	204 No Content	L’arrêt a réussi.
Arrêter une seconde fois web1	POST	304 Not Modified	Le conteneur était déjà arrêté.
Arrêter un conteneur inexistant	POST	404 Not Found	Le conteneur n’existe pas.

Ces résultats correspondent au comportement observé sur l’installation Docker utilisée pendant le TP.

4. Exploration et configuration de NetBox

4.1. Vérification de l’API NetBox

L’interface NetBox est accessible à l’adresse suivante :

http://127.0.0.1:8080/

La racine de son API REST est accessible à l’adresse :

http://127.0.0.1:8080/api/

Une première requête authentifiée a été effectuée à l’aide de Python et du module requests.

Le jeton est lu depuis le fichier local .env et transmis dans l’en-tête HTTP Authorization. Sa valeur n’est pas affichée.

python -c "from pathlib import Path; import requests; c=dict(line.strip().split('=',1) for line in Path('.env').read_text().splitlines() if '=' in line and not line.lstrip().startswith('#')); r=requests.get(c['NETBOX_URL'].rstrip('/')+'/api/', headers={'Authorization':'Bearer '+c['NETBOX_TOKEN']}, timeout=10); print('Code HTTP :',r.status_code); print('Authentification réussie :',r.status_code==200)"

Résultat observé :

Code HTTP : 200
Authentification réussie : True

Ce résultat confirme que NetBox est accessible et que le jeton utilisé permet d’accéder à son API.

4.2. Découverte des endpoints de virtualisation

L’API de virtualisation a été consultée à l’adresse suivante :

http://127.0.0.1:8080/api/virtualization/

La réponse a notamment indiqué la présence des endpoints :

/api/virtualization/cluster-types/
/api/virtualization/clusters/

Le premier permet de gérer les types de clusters. Le second permet de gérer les clusters.

4.3. Consultation des types de clusters

La collection des types de clusters a été consultée dans le navigateur :

http://127.0.0.1:8080/api/virtualization/cluster-types/

Résultat observé : HTTP 200 OK, avec un compteur initial égal à 0.

La réponse indique que la collection est vide avant la création du type Docker.

La méthode OPTIONS a ensuite permis de découvrir les champs attendus par l’API pour une création :

python -c "from pathlib import Path; import requests; c=dict(line.strip().split('=',1) for line in Path('.env').read_text().splitlines() if '=' in line and not line.lstrip().startswith('#')); r=requests.options(c['NETBOX_URL'].rstrip('/')+'/api/virtualization/cluster-types/', headers={'Authorization':'Bearer '+c['NETBOX_TOKEN'], 'Accept':'application/json'}, timeout=10); print('Code HTTP :',r.status_code); print(r.text)"

Résultat observé : HTTP 200 OK.

Les champs obligatoires identifiés sont name et slug.

4.4. Création du type de cluster Docker

Le type de cluster a été créé avec une requête POST. Le corps JSON contient le nom et le slug du type.

python -c "from pathlib import Path; import requests; c=dict(line.strip().split('=',1) for line in Path('.env').read_text().splitlines() if '=' in line and not line.lstrip().startswith('#')); r=requests.post(c['NETBOX_URL'].rstrip('/')+'/api/virtualization/cluster-types/', headers={'Authorization':'Bearer '+c['NETBOX_TOKEN'], 'Content-Type':'application/json', 'Accept':'application/json'}, json={'name':'Docker','slug':'docker'}, timeout=10); print('Code HTTP :',r.status_code); print('Réponse :',r.text)"

Résultat observé : HTTP 201 Created.

Les informations retournées par NetBox confirment la création du type :

Champ	Valeur
Nom	Docker
Slug	docker
Identifiant	1

Le code 201 Created confirme que le nouvel objet a été créé.

4.5. Découverte des champs de création d’un cluster

Avant de créer le cluster, une requête OPTIONS a été envoyée à la collection des clusters :

python -c "from pathlib import Path; import requests; c=dict(line.strip().split('=',1) for line in Path('.env').read_text().splitlines() if '=' in line and not line.lstrip().startswith('#')); u=c['NETBOX_URL'].rstrip('/')+'/api/virtualization/clusters/'; r=requests.options(u, headers={'Authorization':'Bearer '+c['NETBOX_TOKEN'], 'Accept':'application/json'}, timeout=10); print('Code HTTP :',r.status_code); print(r.text)"

Résultat observé : HTTP 200 OK.

La réponse indique notamment que les champs name et type sont obligatoires. Le champ status est facultatif.

Le type Docker ayant l’identifiant 1, cet identifiant peut être utilisé pour associer le cluster à son type.

4.6. Création du cluster docker-local

Le cluster a été créé avec le nom docker-local, le type Docker et le statut active.

python -c "from pathlib import Path; import requests; c=dict(line.strip().split('=',1) for line in Path('.env').read_text().splitlines() if '=' in line and not line.lstrip().startswith('#')); u=c['NETBOX_URL'].rstrip('/')+'/api/virtualization/clusters/'; r=requests.post(u, headers={'Authorization':'Bearer '+c['NETBOX_TOKEN'], 'Accept':'application/json'}, json={'name':'docker-local','type':1,'status':'active'}, timeout=10); print('Code HTTP :',r.status_code); print('Réponse :',r.text)"

Résultat observé : HTTP 201 Created.

Les informations retournées par NetBox confirment les valeurs suivantes :

Champ	Valeur
Nom	docker-local
Type	Docker
Identifiant du type	1
Statut	active
Identifiant du cluster	1

Le cluster a donc été créé et associé au type Docker.

4.7. Vérification du cluster créé

Une première requête sans authentification a été effectuée :

curl -i http://127.0.0.1:8080/api/virtualization/clusters/1/

Résultat observé : HTTP 403 Forbidden, avec un message indiquant que les informations d’authentification sont absentes.

Ce résultat montre que l’endpoint requiert une authentification pour cette requête.

La vérification a ensuite été effectuée avec le jeton stocké dans .env :

python -c "from pathlib import Path; import requests; c=dict(line.strip().split('=',1) for line in Path('.env').read_text().splitlines() if '=' in line and not line.lstrip().startswith('#')); u=c['NETBOX_URL'].rstrip('/')+'/api/virtualization/clusters/1/'; r=requests.get(u, headers={'Authorization':'Bearer '+c['NETBOX_TOKEN'], 'Accept':'application/json'}, timeout=10); print('Code HTTP :',r.status_code); print('Nom du cluster :',r.json().get('name') if r.ok else 'Non disponible'); print('Statut :',r.json().get('status') if r.ok else 'Non disponible')"

Résultat observé :

Code HTTP : 200
Nom du cluster : docker-local
Statut : {'value': 'active', 'label': 'Active'}

Cette vérification confirme que le cluster est enregistré dans NetBox et accessible avec une authentification valide.

5. Sécurité et gestion des secrets

Le jeton API NetBox est stocké dans le fichier local .env.

Ce fichier ne doit pas être envoyé sur GitHub, car il contient des informations sensibles.

Le contrôle suivant a été effectué :

git check-ignore .env

Résultat observé :

.env

Cela confirme que .env est ignoré par Git.

Le fichier .env.example sert de modèle de configuration et peut être versionné à condition de ne contenir aucun secret réel.

Aucun jeton API ni secret ne doit être inscrit dans ce compte rendu.
