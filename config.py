"""
Module config.py - Sauvegarde et chargement de l'état des téléchargements.
Utilise un fichier JSON (pydm_state.json) pour enregistrer la progression
de chaque segment et permettre la reprise après interruption.
"""

import json
import os
from typing import Dict, Optional, List

STATE_FILE = "pydm_state.json"


def save_state(url: str,
               filename: str,
               total_size: int,
               num_segments: int,
               segment_files: List[str]) -> None:
    """
    Sauvegarde l'état d'un téléchargement en cours dans un fichier JSON.

    Args:
        url: L'URL du fichier téléchargé.
        filename: Le nom du fichier de sortie final.
        total_size: Taille totale du fichier en octets.
        num_segments: Nombre de segments.
        segment_files: Liste des chemins des fichiers .partN.
    """
    state = {
        "url": url,
        "filename": filename,
        "total_size": total_size,
        "num_segments": num_segments,
        "segment_files": segment_files,
        "segment_progress": {}
    }

    # Enregistrer la taille déjà téléchargée pour chaque segment
    for i, part_file in enumerate(segment_files):
        if os.path.exists(part_file):
            state["segment_progress"][str(i)] = os.path.getsize(part_file)
        else:
            state["segment_progress"][str(i)] = 0

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

    print(f"[INFO] État sauvegardé dans {STATE_FILE}")


def load_state() -> Optional[Dict]:
    """
    Charge l'état d'un téléchargement précédent s'il existe.

    Returns:
        dict contenant l'état complet, ou None si aucun état trouvé.
    """
    if not os.path.exists(STATE_FILE):
        return None

    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
        return state
    except (json.JSONDecodeError, KeyError):
        print("[ATTENTION] Fichier d'état corrompu, ignoré.")
        return None


def clear_state() -> None:
    """Supprime le fichier d'état après un téléchargement réussi."""
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
        print(f"[INFO] Fichier d'état {STATE_FILE} supprimé.")
