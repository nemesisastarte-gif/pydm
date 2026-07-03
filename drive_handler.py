"""
Module drive_handler.py - Gestionnaire specialise pour Google Drive.
Gere l'extraction du lien de telechargement direct, le contournement
de la page de confirmation de virus, et la gestion des cookies.

Fonctionnement :
1. Extraire l'ID du fichier depuis l'URL Google Drive
2. Utiliser l'API Google Drive (export/download) pour obtenir le lien direct
3. Gerer la page de confirmation pour les gros fichiers (>100 Mo)
4. Transmettre les cookies et referer necessaires au download_manager
"""

import re
import requests
from typing import Optional, Tuple
from urllib.parse import urlparse, parse_qs


def extract_drive_id(url: str) -> Optional[str]:
    """
    Extrait l'ID du fichier depuis une URL Google Drive.
    
    Formes supportees :
    - https://drive.google.com/file/d/FILE_ID/view
    - https://drive.google.com/open?id=FILE_ID
    - https://docs.google.com/.../d/FILE_ID/...
    
    Returns:
        L'ID du fichier ou None si non trouve.
    """
    patterns = [
        r'/file/d/([a-zA-Z0-9_-]+)',
        r'/d/([a-zA-Z0-9_-]+)',
        r'[?&]id=([a-zA-Z0-9_-]+)',
        r'/folders/([a-zA-Z0-9_-]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def is_google_drive_url(url: str) -> bool:
    """Verifie si l'URL provient de Google Drive."""
    parsed = urlparse(url)
    return any(domain in parsed.netloc for domain in [
        'drive.google.com',
        'docs.google.com',
        'google.com/drive',
    ])


def get_direct_download_url(drive_id: str, confirm_code: str = None) -> Tuple[Optional[str], dict]:
    """
    Obtient le lien de telechargement direct pour un fichier Google Drive.
    
    Pour les petits fichiers (<100 Mo) : telechargement direct possible.
    Pour les gros fichiers : necessite de passer par la page de confirmation
    et d'obtenir un token de verification (confirm_code).
    
    Args:
        drive_id: L'ID du fichier Google Drive.
        confirm_code: Token de confirmation pour les gros fichiers (optionnel).
    
    Returns:
        Tuple (url_directe, headers_necessaires)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # URL de telechargement standard
    base_url = f"https://drive.google.com/uc?export=download&id={drive_id}"
    
    if confirm_code:
        base_url += f"&confirm={confirm_code}"
    
    return base_url, headers


def get_confirm_token(session: requests.Session, drive_id: str) -> Optional[str]:
    """
    Pour les fichiers > 100 Mo, Google affiche une page intermediaire
    avec un token de confirmation. Cette fonction extrait ce token.
    
    Args:
        session: Session requests avec les cookies eventuels.
        drive_id: L'ID du fichier.
    
    Returns:
        Le token de confirmation ou None.
    """
    url = f"https://drive.google.com/uc?export=download&id={drive_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = session.get(url, headers=headers, timeout=10)
        
        # Chercher le token dans la page HTML
        # Pattern: <input type="hidden" name="confirm" value="t">
        # ou: confirm=XXXXX dans l'URL de la page
        match = re.search(r'name="confirm"\s+value="([^"]+)"', response.text)
        if match:
            return match.group(1)
        
        match = re.search(r'confirm=([a-zA-Z0-9_-]+)', response.text)
        if match:
            return match.group(1)
            
    except requests.exceptions.RequestException as e:
        print(f"[DRIVE] Erreur lors de la recuperation du token : {e}")
    
    return None


def get_file_metadata(drive_id: str, api_key: str = None) -> Optional[dict]:
    """
    Utilise l'API Google Drive pour obtenir les metadonnees du fichier.
    
    Args:
        drive_id: L'ID du fichier.
        api_key: Cle API Google (optionnelle, necessite un compte Google Cloud).
    
    Returns:
        Dictionnaire avec les metadonnees ou None.
    """
    if not api_key:
        # Sans cle API, on essaie de recuperer le nom depuis la page
        url = f"https://drive.google.com/file/d/{drive_id}/view"
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            # Chercher le titre dans la page
            match = re.search(r'<title>(.*?)</title>', response.text)
            if match:
                title = match.group(1)
                # Google ajoute " - Google Drive" a la fin
                title = title.replace(" - Google Drive", "").strip()
                return {"name": title, "size": None}
        except Exception:
            pass
        return None
    
    # Avec cle API
    api_url = f"https://www.googleapis.com/drive/v3/files/{drive_id}"
    params = {
        "key": api_key,
        "fields": "name,size,mimeType"
    }
    
    try:
        response = requests.get(api_url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"[DRIVE] Erreur API : {e}")
    
    return None


def resolve_drive_url(url: str, cookies: dict = None) -> Optional[dict]:
    """
    Point d'entree principal : resout une URL Google Drive en
    toutes les informations necessaires pour lancer le telechargement.
    
    Args:
        url: URL Google Drive complete.
        cookies: Dictionnaire de cookies (optionnel, pour fichiers prives).
    
    Returns:
        Dictionnaire avec :
        {
            "direct_url": str,
            "filename": str,
            "size": int ou None,
            "headers": dict (headers HTTP a utiliser),
            "cookies": dict
        }
        ou None si echec.
    """
    drive_id = extract_drive_id(url)
    if not drive_id:
        print("[DRIVE] Impossible d'extraire l'ID du fichier.")
        return None
    
    print(f"[DRIVE] ID extrait : {drive_id}")
    
    # Creer une session avec les cookies fournis
    session = requests.Session()
    if cookies:
        for name, value in cookies.items():
            session.cookies.set(name, value, domain=".google.com")
    
    # Recuperer les metadonnees si possible
    metadata = get_file_metadata(drive_id)
    filename = metadata.get("name", f"drive_{drive_id}.bin") if metadata else f"drive_{drive_id}.bin"
    file_size = metadata.get("size") if metadata else None
    
    # Obtenir l'URL de telechargement direct
    direct_url, base_headers = get_direct_download_url(drive_id)
    
    # Verifier si un token de confirmation est necessaire (gros fichiers)
    confirm_token = get_confirm_token(session, drive_id)
    if confirm_token:
        print(f"[DRIVE] Token de confirmation obtenu : {confirm_token}")
        direct_url, base_headers = get_direct_download_url(drive_id, confirm_token)
    
    result = {
        "direct_url": direct_url,
        "filename": filename,
        "size": file_size,
        "headers": base_headers,
        "cookies": dict(session.cookies.get_dict())
    }
    
    print(f"[DRIVE] URL directe : {direct_url}")
    print(f"[DRIVE] Nom du fichier : {filename}")
    
    return result
