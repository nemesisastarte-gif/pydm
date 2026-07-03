# PyDM - Python Download Manager

Gestionnaire de téléchargements inspiré d'IDM pour Linux.
Téléchargement segmenté multithread, détection automatique,
extension navigateur, et contournement de restrictions.

## Fonctionnalités

- **Téléchargement segmenté** : Découpe les fichiers en 4-32 segments téléchargés en parallèle
- **Reprise automatique** : Reprend les téléchargements interrompus
- **Détection presse-papiers** : Surveille les URLs copiées
- **Extension navigateur** : Intercepte les téléchargements depuis Firefox/Chrome
- **Google Drive** : Contourne la page de confirmation pour les gros fichiers
- **Franime/streaming** : Extrait les URLs vidéo des pages de streaming anime
- **Mode interactif** : Interface pas-à-pas guidée

## Installation rapide

```bash
git clone https://github.com/nemesisastarte-gif/pydm.git
cd pydm
chmod +x install.sh
./install.sh
```

## Utilisation

```bash
pydm download "https://exemple.com/fichier.zip"    # Téléchargement direct
pydm download "https://exemple.com/fichier.zip" -n 8  # 8 segments
pydm interactive                                     # Mode pas-à-pas
pydm clipboard                                       # Surveiller le presse-papiers
pydm ws-server                                       # Serveur pour extension navigateur
pydm drive "https://drive.google.com/..." --download # Google Drive
pydm franime "https://franime.fr/..." --download     # Streaming anime
pydm resume                                          # Reprendre un téléchargement
pydm clean                                           # Nettoyer les fichiers temporaires
```

## Extension navigateur

1. Lance `pydm ws-server` dans un terminal
2. Ouvre `about:debugging` (Firefox) ou `chrome://extensions` (Chrome)
3. Active "Mode développeur"
4. Charge l'extension depuis le dossier `extension/`
5. Les téléchargements sont automatiquement interceptés

## Architecture

```
pydm/
├── main.py                 # CLI unifiée (8 commandes)
├── download_manager.py     # Orchestrateur parallèle
├── segment_downloader.py   # Téléchargeur de plage d'octets
├── http_utils.py           # Requêtes HEAD/GET avec fallback
├── config.py               # Sauvegarde/reprise JSON
├── clipboard_monitor.py    # Surveillance presse-papiers
├── websocket_server.py     # Serveur WebSocket RFC 6455
├── drive_handler.py        # Résolveur Google Drive
├── franime_handler.py      # Extracteur vidéo streaming
├── extension/              # Extension navigateur
└── install.sh              # Script d'installation
```

## Dépendances

- Python 3.8+
- `requests` (pip install requests)
- `xclip` (pour la surveillance du presse-papiers)

## Licence

MIT
