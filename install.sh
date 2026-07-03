#!/bin/bash
# ============================================================
# PyDM - Script d'installation automatique
# Installe les dépendances, crée l'alias, et vérifie tout
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

PYDM_DIR="$(cd "$(dirname "$0")" && pwd)"
echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}  PyDM - Installation${NC}"
echo -e "${CYAN}  Dossier : ${PYDM_DIR}${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""

# ----------------------------------------------------------
# Étape 1 : Vérifier Python 3
# ----------------------------------------------------------
echo -e "${CYAN}[1/5] Vérification de Python 3...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON=$(command -v python3)
    echo -e "${GREEN}  OK : Python 3 trouvé ($($PYTHON --version))${NC}"
else
    echo -e "${RED}  ERREUR : Python 3 non trouvé. Installez-le d'abord.${NC}"
    exit 1
fi

# ----------------------------------------------------------
# Étape 2 : Installer requests si nécessaire
# ----------------------------------------------------------
echo -e "${CYAN}[2/5] Vérification de la bibliothèque requests...${NC}"
if $PYTHON -c "import requests" 2>/dev/null; then
    echo -e "${GREEN}  OK : requests déjà installé${NC}"
else
    echo "  Installation de requests..."
    $PYTHON -m pip install requests --user 2>/dev/null || \
    $PYTHON -m pip install requests --break-system-packages 2>/dev/null || \
    sudo apt install python3-requests -y 2>/dev/null || \
    sudo pacman -S python-requests --noconfirm 2>/dev/null || \
    echo -e "${RED}  ATTENTION : Impossible d'installer requests automatiquement.${NC}"
    echo "  Faites : pip install requests"
fi

# ----------------------------------------------------------
# Étape 3 : Installer xclip (presse-papiers)
# ----------------------------------------------------------
echo -e "${CYAN}[3/5] Vérification de xclip (surveillance presse-papiers)...${NC}"
if command -v xclip &> /dev/null; then
    echo -e "${GREEN}  OK : xclip déjà installé${NC}"
else
    echo "  Installation de xclip..."
    sudo apt install xclip -y 2>/dev/null || \
    sudo pacman -S xclip --noconfirm 2>/dev/null || \
    echo -e "${RED}  ATTENTION : Installez xclip manuellement pour la surveillance du presse-papiers.${NC}"
fi

# ----------------------------------------------------------
# Étape 4 : Créer l'alias pydm
# ----------------------------------------------------------
echo -e "${CYAN}[4/5] Création de l'alias 'pydm'...${NC}"

ALIAS_LINE="alias pydm='python3 ${PYDM_DIR}/main.py'"

# Supprimer les anciens alias pydm
sed -i '/^alias pydm=/d' ~/.bashrc 2>/dev/null || true
sed -i '/^alias pydm=/d' ~/.bash_aliases 2>/dev/null || true
sed -i '/^alias pydm=/d' ~/.profile 2>/dev/null || true

# Ajouter dans .bashrc
echo "$ALIAS_LINE" >> ~/.bashrc
echo -e "${GREEN}  OK : Alias ajouté dans ~/.bashrc${NC}"

# Ajouter aussi dans .bash_aliases si le fichier existe
if [ -f ~/.bash_aliases ]; then
    echo "$ALIAS_LINE" >> ~/.bash_aliases
    echo -e "${GREEN}  OK : Alias ajouté dans ~/.bash_aliases${NC}"
fi

# ----------------------------------------------------------
# Étape 5 : Vérification finale
# ----------------------------------------------------------
echo -e "${CYAN}[5/5] Vérification de l'installation...${NC}"
$PYTHON -c "
import sys
sys.path.insert(0, '${PYDM_DIR}')
try:
    from main import *  # noqa
    print('  Modules OK')
except Exception as e:
    print(f'  ERREUR: {e}')
    sys.exit(1)
"
echo -e "${GREEN}  OK : Tous les modules Python sont valides${NC}"

# ----------------------------------------------------------
# Résumé
# ----------------------------------------------------------
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  Installation terminée !${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo "  Pour activer l'alias immédiatement :"
echo -e "    ${CYAN}source ~/.bashrc${NC}"
echo ""
echo "  Commandes disponibles :"
echo "    pydm download <url>       Télécharger un fichier"
echo "    pydm interactive          Mode pas-à-pas"
echo "    pydm clipboard            Surveiller le presse-papiers"
echo "    pydm ws-server            Serveur pour extension navigateur"
echo "    pydm drive <url>          Google Drive"
echo "    pydm franime <url>        Streaming anime"
echo "    pydm resume               Reprendre un téléchargement"
echo "    pydm clean                Nettoyer les fichiers temporaires"
echo ""
