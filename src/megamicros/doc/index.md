Ce dépôt regroupe les pilotes logicielles facilitant l'utilisation des systèmes d'acquisition Megamicros.

## Téléchargement du dépôt depuis GitHub

### (Optionnel) Création d'un environnement virtuel

Pour isoler l'installation des pilotes Megamicros de votre système d'exploitation, il est fortement recommandé de travailler dans un environnement virtuel annexe.
Nous utilisons pour cela le module `python3-venv`, intégrée nativement dans les distributions Python >= 3.3.
Pour créer un environnement virtuel, dans un terminal, déplacer vous dans votre dossier de travail puis lancez la commande suivante :
```
python3 -m venv /path/to/venv
```  
L'environnement sera initialisé dans un dossier `venv` situé dans le dossier `/path/to`.
Pour l'activer et commencer à travailler dans celui-ci :
```
source /path/to/venv/bin/activate
```
Des programmes comme `virtualenvwrapper` permettent une gestion efficaces de l'ensemble de vos environnements virtuels (https://virtualenvwrapper.readthedocs.io/en/latest/).   
   
---
**_UNIX UNIQUEMENT : _** Si vous souhaitez accéder aux appels binaires sans activer votre environnement virtuel, vous devez ajouter à la fin de votre fichier `~/.bashrc` la ligne suivante :
```
export PATH=/path/to/venv/bin:$PATH
```
---

### Installation via pip

Une fois votre environnement activé, vous pouvez cloner le dépôt Bitbucket :
```
git clone https://hugodemontis@bitbucket.org/marchi/megamicros.git
```
L'installateur se situe dans la branche distante "easy_install". Pour basculer sur cette branche :
```
git fetch
git checkout easy_install
```
L'installation dans votre environnement actif est réalisée via la commande :
```
pip install .
```   
Vous pouvez vérifier que le module est bien installé via la commande `pip list`.

### Installation via Docker

L'installation des logiciels Megamicros peut également s'effectuer à travers un conteneur Docker. 
Le client Docker doit être installé au préalable sur la machine-hôte (https://docs.docker.com/engine/install/).

La commande suivante permet de construire le conteneur Megamicros d'après le fichier `Dockerfile` :
```
docker build -t megamicros .
```
L'image ainsi créée se nomme `megamicros`, pour être identifié plus facilement.  

Pour lancer un conteneur à partir de cette image :
```
docker run --rm --device=/dev/bus/usb:/dev/bus/usb -v ~/Data:/home/data --name megamicros megamicros <command>
```
- `--rm` : suppression du conteneur s'il existe au préalable.
- `--device` : connexion logique entre les entrées de la machine-hôte et du conteneur actif (nécessaire pour autoriser les droits d'écriture)
- `-v` : connexion logique entre le dossier de la machine hôte et le dossier dans le conteneur (permet l'échange direct de fichiers)
- `--name`: nom du conteneur actif, pour l'identifier plus facilement
- `<command>` : commande à lancer dès l'exécution du conteneur, par exemple le terminal via la commande `bash`

## Prise en main

### Première acquisition

Assurez-vous que votre système Megamicros est branché sur la machine-hôte via USB. Pour lancer une acquisition via le terminal :
```
megamicros <version> -d 5 -v
```
où `<version>` indique le nombre de voies géré par votre système (32, 128, 256 ou 1024).


### Module d'aide

Pour accéder au module d'aide via le terminal :
```
megamicros --help
```
