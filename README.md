# GPX Komoot Studio

Outils locaux pour synchroniser des parcours Komoot en GPX, les organiser dans une bibliothèque versionnée, puis conserver les versions éditées avec [gpx.studio](https://gpx.studio).

Le téléchargement est assuré par [KomootGPX](https://github.com/timschneeb/KomootGPX), un outil communautaire qui s’appuie sur des endpoints Komoot non documentés.

## Installation

Prérequis : Python 3.10 ou plus récent et [uv](https://docs.astral.sh/uv/getting-started/installation/).

Depuis la racine du dépôt :

```bash
uv sync
```

`uv` installe les dépendances déclarées dans `pyproject.toml`, crée l’environnement `.venv/` et expose la commande du projet. Il n’est pas nécessaire d’activer l’environnement.

## Utilisation

### Parcourir la bibliothèque dans un navigateur

Depuis la racine du dépôt, lancez le serveur local :

```bash
uv run komoot-library web
```

Ouvrez ensuite <http://127.0.0.1:8765>. La page liste les parcours et leurs fichiers GPX, permet de rechercher par titre, identifiant ou nom de fichier, et propose le téléchargement de chaque version. Le bouton **Ouvrir gpx.studio** ouvre l’éditeur en ligne dans un nouvel onglet ; téléchargez d’abord le GPX voulu, puis importez-le dans gpx.studio. Le navigateur n’autorise pas le site gpx.studio à lire directement les fichiers de cette bibliothèque locale.

Le serveur s’arrête avec `Ctrl+C`. Pour choisir un autre port :

```bash
uv run komoot-library web --port 9000
```

Par défaut, le serveur n’est accessible que depuis la machine locale. Pour l’ouvrir sur le réseau local :

```bash
uv run komoot-library web --host 0.0.0.0
```

Dans ce cas, toute personne pouvant joindre le serveur peut consulter et télécharger les GPX ; utilisez-le uniquement sur un réseau de confiance et ne redirigez pas ce port vers Internet.

### Catalogue et gpx.studio auto-hébergés avec Docker Compose

gpx.studio est construit depuis ses sources amont : le projet ne fournit pas d’image Docker officielle. Compose démarre le catalogue, construit gpx.studio et sert les deux sous la même origine. Le bouton **Ouvrir dans gpx.studio** peut ainsi transmettre directement l’URL du GPX sélectionné à l’éditeur.

1. Construisez et démarrez les services :

   ```bash
   docker compose up --build -d
   ```

2. Ouvrez <http://localhost:8080/library/>. gpx.studio est aussi disponible à la racine <http://localhost:8080/> ; son sélecteur de langue permet de choisir Français. Le catalogue propose également Français ou English pour les liens **Ouvrir dans gpx.studio**. Le port `8765` du catalogue n’est pas publié sur l’hôte dans Compose ; l’éditeur et le catalogue sont servis sous la même origine pour charger directement le GPX choisi.

#### Ajouter un fond MapTiler

Les fonds libres intégrés suffisent pour un usage courant. Vous pouvez aussi ajouter un fond personnalisé fourni par MapTiler avec une clé API.

La clé MapTiler n’ajoute pas de fond automatiquement et n’est pas utilisée par le fond par défaut. Pour l’utiliser, ajoutez un fond personnalisé dans gpx.studio :

1. Créez une clé dans [MapTiler Cloud](https://cloud.maptiler.com/account/keys/). Dans **Allowed HTTP Origins**, ajoutez `localhost` et `127.0.0.1`, chacun sur sa propre ligne ; ne renseignez pas le protocole ni le port. Laissez **Allowed user-agent header** vide.
2. Ouvrez gpx.studio, puis les réglages des couches et la section **Custom layers**.
3. Créez une couche de type **Basemap**, nommez-la par exemple `MapTiler Streets`, et ajoutez cette URL en remplaçant `VOTRE_CLE` par la clé :

   ```text
   https://api.maptiler.com/maps/streets-v4/style.json?key=VOTRE_CLE
   ```

4. Enregistrez la couche et sélectionnez-la comme fond de carte. Elle est conservée dans les réglages locaux du navigateur.

La clé est publique car utilisée par le navigateur. La limiter aux origines locales réduit les usages depuis d’autres sites. Le fichier `.env` n’est pas nécessaire pour cette configuration personnalisée.

Arrêter les services :

```bash
docker compose down
```

Le port est publié uniquement sur `127.0.0.1` et la bibliothèque est montée en lecture seule dans le service web. Pour mettre à jour la révision gpx.studio, changez `GPX_STUDIO_REF` dans `Dockerfile.gpxstudio`, puis reconstruisez avec `docker compose up --build -d`.

### Synchroniser Komoot

Depuis la racine du dépôt :

```bash
uv run komoot-library sync
```

À la première utilisation, KomootGPX demande les identifiants Komoot. Il gère le jeton de session dans le cache local de l’utilisateur, en dehors du dépôt ; il peut redemander une authentification lorsque ce jeton expire.

La première sync télécharge les parcours. Les suivantes utilisent `-S` pour ignorer ceux que KomootGPX considère inchangés. Les GPX bruts et persistants sont conservés dans `komoot-library/.sync_cache/` : **ne supprimez pas ce dossier** si vous voulez éviter de télécharger à nouveau tous les parcours. Le cache d’empreintes propre à KomootGPX se trouve lui aussi dans le cache local de l’utilisateur.

Le script copie vers `tours/<id>/` les GPX qui viennent d’être téléchargés ou dont le fichier de destination manque, puis met à jour `meta.json`. Les GPX inchangés ne sont pas réécrits.

### Filtrer les parcours

Par défaut, la sync traite tous les types de parcours. Pour synchroniser uniquement les parcours planifiés, passez le filtre KomootGPX après `--` :

```bash
uv run komoot-library sync --tour-type planned -- -a -S -t planned
```

Pour les parcours enregistrés :

```bash
uv run komoot-library sync --tour-type recorded -- -a -S -t recorded
```

`--tour-type` choisit le nom et le rôle des fichiers dans la bibliothèque ; `-t` filtre les parcours téléchargés par KomootGPX. Pour passer d’autres options KomootGPX, utilisez également `--` :

```bash
uv run komoot-library sync -- -a -S --start-date 2026-01-01
```

Lorsque des arguments KomootGPX sont fournis, ils remplacent les options par défaut `-a -S`. Ajoutez `-S` explicitement si vous souhaitez conserver la détection des parcours inchangés ; évitez `-s`, qui saute les fichiers déjà présents dans le dossier de sortie au lieu de vérifier les changements.

### Enregistrer une version éditée

Après avoir exporté le GPX depuis gpx.studio, ajoutez-le à la bibliothèque :

```bash
uv run komoot-library add-gpxstudio \
  --tour-id 12345678 \
  --source ~/Downloads/ma_route.gpx
```

Le script copie le fichier dans `komoot-library/tours/12345678/`, lui attribue le prochain préfixe numérique disponible (`NN_gpxstudio_YYYY-MM-DD.gpx`) et actualise `meta.json`. La date est celle du jour en UTC par défaut ; elle peut être fournie explicitement :

```bash
uv run komoot-library add-gpxstudio \
  --tour-id 12345678 \
  --source ./edit.gpx \
  --date 2026-04-15
```

## Référence technique

### Arborescence

```text
komoot-library/
  .sync_cache/             # GPX bruts nécessaires aux syncs incrémentales (ignoré par Git)
  tours/
    <komoot_tour_id>/
      meta.json
      01_komoot_sync.gpx   # type all
      01_komoot_planned.gpx # type planned
      02_komoot_recorded.gpx # type recorded
      NN_gpxstudio_YYYY-MM-DD.gpx
```

Les noms Komoot dépendent du `--tour-type` du script :

| `--tour-type` | Fichier Komoot | Rôle dans `meta.json` |
| --- | --- | --- |
| `all` (défaut) | `01_komoot_sync.gpx` | `komoot_export` |
| `planned` | `01_komoot_planned.gpx` | `planned` |
| `recorded` | `02_komoot_recorded.gpx` | `recorded` |

Le type `all` regroupe les GPX téléchargés sous le nom `01_komoot_sync.gpx`. Pour séparer les parcours planifiés et enregistrés, faites deux syncs avec le filtre KomootGPX correspondant (`-t planned` et `-t recorded`) et le `--tour-type` correspondant.

### Métadonnées `meta.json`

Un fichier `meta.json` est créé ou actualisé dans chaque dossier de parcours :

| Champ | Description |
| --- | --- |
| `komoot_id` | Identifiant numérique Komoot |
| `title` | Premier nom trouvé dans le GPX, si disponible |
| `url` | URL du parcours Komoot |
| `last_sync` | Date UTC de la dernière mise à jour du GPX par le script |
| `source_tool` | Outil source, par défaut `komootgpx` |
| `files` | Fichiers suivis, chacun avec `path`, `role` et `updated_at` |

Rôles utilisés : `planned`, `recorded`, `komoot_export` et `edited_gpxstudio`. Les chemins `path` sont relatifs au dossier du parcours.

### Options générales

```bash
uv run komoot-library --help
uv run komoot-library web --help
uv run komoot-library sync --help
uv run komoot-library add-gpxstudio --help
```

La racine de la bibliothèque est `komoot-library/` à la racine du dépôt par défaut. Elle peut être remplacée par la variable d’environnement `KOMOOT_LIBRARY` ou par l’option globale `--library` :

```bash
uv run komoot-library --library /chemin/vers/ma-bibliotheque sync
```

L’option doit précéder la sous-commande.

## Limites et sécurité

- KomootGPX est un outil communautaire basé sur des endpoints non documentés ; une évolution de Komoot peut interrompre la sync.
- L’édition dans gpx.studio ne met pas automatiquement à jour le parcours Komoot : le réimport dans Komoot reste manuel ([aide Komoot](https://support.komoot.com/hc/en-us/articles/360022834132-Export-and-import-GPS-files)).
- Le cache local KomootGPX contient des informations de session ; ne le partagez pas et ne le commitez pas.
- Sauvegardez régulièrement `komoot-library/`, en particulier `tours/`. `.sync_cache/` peut être reconstruit en retéléchargeant les GPX, mais cela implique une sync complète.
