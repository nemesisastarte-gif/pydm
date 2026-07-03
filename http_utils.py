"""
Module http_utils.py - Outils reseau pour interroger le serveur cible.
Envoie une requete HEAD (puis GET partiel en fallback) pour obtenir
la taille du fichier et verifier si le serveur supporte le telechargement
par plages (Range).
"""

import requests
from typing import Tuple, Optional


def get_file_info(url: str, cookies: dict = None, extra_headers: dict = None) -> Tuple[Optional[int], bool]:
    """
    Interroge le serveur pour obtenir :
    - La taille totale du fichier (Content-Length)
    - Le support de la reprise par plages (Accept-Ranges: bytes)

    Args:
        url: L'URL complete du fichier a telecharger.
        cookies: Dictionnaire de cookies optionnel.
        extra_headers: Headers HTTP supplementaires (Referer, etc.)

    Returns:
        Tuple[Optional[int], bool]:
            - int : taille en octets (None si non disponible)
            - bool: True si le serveur supporte le telechargement par plages
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Encoding": "identity",
    }
    
    if extra_headers:
        headers.update(extra_headers)

    # Tentative 1 : HEAD
    try:
        response = requests.head(
            url, headers=headers, cookies=cookies,
            timeout=15, allow_redirects=True
        )
        if response.status_code < 400:
            content_length = response.headers.get("Content-Length")
            accept_ranges = response.headers.get("Accept-Ranges", "")
            if content_length and content_length.isdigit():
                return int(content_length), "bytes" in accept_ranges.lower()
    except requests.exceptions.RequestException:
        pass

    # Tentative 2 : GET avec Range bytes=0-0 (1 seul octet)
    headers["Range"] = "bytes=0-0"
    try:
        response = requests.get(
            url, headers=headers, cookies=cookies,
            timeout=15, allow_redirects=True, stream=True
        )
        if response.status_code in (200, 206):
            content_length = None
            
            content_range = response.headers.get("Content-Range", "")
            if content_range and "/" in content_range:
                total = content_range.split("/")[-1].strip()
                if total.isdigit():
                    content_length = int(total)

            if not content_length:
                cl = response.headers.get("Content-Length")
                if cl and cl.isdigit():
                    content_length = int(cl)

            accept_ranges = response.headers.get("Accept-Ranges", "")
            supports_resume = "bytes" in accept_ranges.lower() or response.status_code == 206
            
            response.close()
            return content_length, supports_resume

    except requests.exceptions.RequestException:
        pass
    finally:
        headers.pop("Range", None)

    # Tentative 3 : GET simple, on lit juste les headers sans telecharger
    try:
        response = requests.get(
            url, headers=headers, cookies=cookies,
            timeout=15, allow_redirects=True, stream=True
        )
        response.raise_for_status()
        
        content_length = response.headers.get("Content-Length")
        file_size = int(content_length) if content_length and content_length.isdigit() else None
        
        accept_ranges = response.headers.get("Accept-Ranges", "")
        
        response.close()
        return file_size, "bytes" in accept_ranges.lower()

    except requests.exceptions.RequestException as e:
        print(f"[ERREUR] Impossible de joindre le serveur : {e}")
        return None, False
