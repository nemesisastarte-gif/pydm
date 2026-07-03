"""
Module franime_handler.py - Gestionnaire specialise pour Franime
et sites de streaming anime similaires.

Fonctionnement :
1. Analyser la page HTML pour trouver les iframes de lecteurs video
2. Extraire les URLs des videos hebergees (Uqload, Sendvid, etc.)
3. Fouiller les scripts JavaScript pour trouver les .m3u8 ou .mp4
4. Resoudre les URLs de streaming en liens de telechargement direct

Supporte :
- Franime.fr / Franime.xyz
- Uqload (hebergeur commun)
- Sendvid / Doodstream (hebergeurs)
- Voe / Streamwish
- Lecteurs JW Player / VideoJS
"""

import re
import requests
import json
import base64
from typing import Optional, List, Dict
from urllib.parse import urljoin, urlparse, parse_qs


# User-Agent pour simuler un navigateur
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
    "Referer": "https://www.google.com/",
}


def is_franime_url(url: str) -> bool:
    """Verifie si l'URL provient de Franime ou similaire."""
    parsed = urlparse(url)
    return any(name in parsed.netloc.lower() for name in [
        'franime', 'anime', 'mavanime', 'vostfree',
        'animesama', 'jetanime', 'neko-sama'
    ])


def is_video_hosting_url(url: str) -> bool:
    """Verifie si l'URL pointe vers un hebergeur video connu."""
    parsed = urlparse(url)
    hosters = [
        'uqload', 'sendvid', 'doodstream', 'dood', 'voe',
        'streamwish', 'vidmoly', 'upstream', 'mixdrop',
        'vidlox', 'vidoza', 'streamtape', 'vidcloud',
        'mp4upload', 'yourupload', 'ok.ru', 'vk.com',
        'myvi', 'filemoon', 'vudeo', 'wolfstream'
    ]
    return any(hoster in parsed.netloc.lower() for hoster in hosters)


def extract_iframe_urls(html: str, base_url: str) -> List[str]:
    """
    Extrait toutes les URLs d'iframes depuis le HTML d'une page.
    Les sites de streaming utilisent des iframes pour integrer
    les lecteurs video externes.
    """
    iframe_urls = []
    
    # Pattern iframe classique
    iframe_patterns = [
        r'<iframe[^>]+src=["\']([^"\']+)["\']',
        r'<iframe[^>]+data-src=["\']([^"\']+)["\']',
        r'<embed[^>]+src=["\']([^"\']+)["\']',
    ]
    
    for pattern in iframe_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            # Resoudre les URLs relatives
            full_url = urljoin(base_url, match)
            if full_url.startswith("http"):
                iframe_urls.append(full_url)
    
    return list(set(iframe_urls))  # Deduplication


def extract_video_from_javascript(html: str) -> List[str]:
    """
    Cherche des URLs de videos dans le code JavaScript de la page.
    Les lecteurs comme JW Player ou VideoJS stockent les URLs
    dans des variables JavaScript ou des blocs JSON.
    """
    video_urls = []
    
    # Patterns pour trouver des URLs .mp4, .m3u8, .mkv
    url_patterns = [
        r'["\'](https?://[^"\']+\.(?:mp4|mkv|webm|m3u8|ts)[^"\']*)["\']',
        r'file\s*:\s*["\']([^"\']+)["\']',
        r'sources\s*:\s*\[[^\]]*["\'](https?://[^"\']+)["\']',
        r'url\s*:\s*["\']([^"\']+)["\']',
        r'videoUrl\s*=\s*["\']([^"\']+)["\']',
        r'video_url\s*:\s*["\']([^"\']+)["\']',
        r'streamUrl\s*:\s*["\']([^"\']+)["\']',
    ]
    
    for pattern in url_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            if match.startswith("http") and not match.endswith((".png", ".jpg", ".gif", ".css", ".js")):
                video_urls.append(match)
    
    return list(set(video_urls))


def decode_base64_url(encoded: str) -> Optional[str]:
    """Tente de decoder une URL encodee en base64 (courant sur les sites de streaming)."""
    try:
        # Ajouter le padding si necessaire
        padding = 4 - len(encoded) % 4
        if padding != 4:
            encoded += "=" * padding
        decoded = base64.b64decode(encoded).decode("utf-8")
        if decoded.startswith("http"):
            return decoded
    except Exception:
        pass
    return None


def resolve_uqload(url: str) -> Optional[Dict]:
    """
    Resout une URL Uqload pour obtenir le lien video direct.
    Uqload est un hebergeur couramment utilise par Franime.
    """
    headers = BROWSER_HEADERS.copy()
    headers["Referer"] = "https://franime.fr/"
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        html = response.text
        
        # Uqload stocke l'URL dans une variable JavaScript
        # Pattern: player.source = {"file": "https://..."}
        match = re.search(r'["\']file["\']\s*:\s*["\']([^"\']+)["\']', html)
        if match:
            video_url = match.group(1)
            return {
                "direct_url": video_url,
                "filename": video_url.split("/")[-1].split("?")[0] or "video.mp4",
                "headers": headers,
                "host": "uqload"
            }
        
        # Essayer pattern alternatif : sources: [{file: "..."}]
        match = re.search(r'sources\s*:\s*\[\s*\{\s*["\']file["\']\s*:\s*["\']([^"\']+)["\']', html)
        if match:
            video_url = match.group(1)
            return {
                "direct_url": video_url,
                "filename": "video_uqload.mp4",
                "headers": headers,
                "host": "uqload"
            }
            
    except Exception as e:
        print(f"[FRANIME] Erreur Uqload : {e}")
    
    return None


def resolve_generic_host(url: str, referer: str = "https://franime.fr/") -> Optional[Dict]:
    """
    Resout un hebergeur generique en fouillant la page pour
    trouver l'URL de la video.
    """
    headers = BROWSER_HEADERS.copy()
    headers["Referer"] = referer
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        html = response.text
        
        # Chercher toutes les URLs video dans la page
        video_urls = extract_video_from_javascript(html)
        
        if video_urls:
            # Prendre la premiere URL video trouvee
            video_url = video_urls[0]
            return {
                "direct_url": video_url,
                "filename": video_url.split("/")[-1].split("?")[0] or "video.mp4",
                "headers": headers,
                "host": urlparse(url).netloc
            }
        
    except Exception as e:
        print(f"[FRANIME] Erreur hebergeur generique : {e}")
    
    return None


def resolve_franime_page(url: str, episode: str = None) -> List[Dict]:
    """
    Point d'entree principal : analyse une page Franime et
    retourne toutes les sources video trouvees.
    
    Args:
        url: URL de la page Franime (episode ou serie).
        episode: Numero d'episode specifique (optionnel).
    
    Returns:
        Liste de dictionnaires contenant les informations de chaque source video :
        [{"direct_url": ..., "filename": ..., "headers": {...}, "host": ...}, ...]
    """
    results = []
    headers = BROWSER_HEADERS.copy()
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        html = response.text
    except Exception as e:
        print(f"[FRANIME] Erreur lors du chargement de la page : {e}")
        return results
    
    print(f"[FRANIME] Page chargee ({len(html)} caracteres)")
    
    # 1. Extraire les iframes (lecteurs video heberges)
    iframes = extract_iframe_urls(html, url)
    print(f"[FRANIME] {len(iframes)} iframe(s) trouvee(s)")
    
    for iframe_url in iframes:
        if "uqload" in iframe_url.lower():
            result = resolve_uqload(iframe_url)
        elif is_video_hosting_url(iframe_url):
            result = resolve_generic_host(iframe_url)
        else:
            continue
        
        if result:
            results.append(result)
    
    # 2. Chercher les URLs video directement dans le JS de la page
    direct_videos = extract_video_from_javascript(html)
    for video_url in direct_videos:
        if video_url.endswith((".mp4", ".mkv", ".webm")):
            results.append({
                "direct_url": video_url,
                "filename": video_url.split("/")[-1].split("?")[0] or "video.mp4",
                "headers": headers,
                "host": "direct"
            })
    
    # 3. Chercher des URLs encodees en base64 dans la page
    b64_patterns = re.findall(r'["\']([A-Za-z0-9+/=]{20,})["\']', html)
    for b64_str in b64_patterns:
        decoded = decode_base64_url(b64_str)
        if decoded and (decoded.endswith(".mp4") or "video" in decoded.lower()):
            results.append({
                "direct_url": decoded,
                "filename": decoded.split("/")[-1].split("?")[0] or "video.mp4",
                "headers": headers,
                "host": "base64_decoded"
            })
    
    # Deduplication par URL directe
    seen = set()
    unique_results = []
    for r in results:
        if r["direct_url"] not in seen:
            seen.add(r["direct_url"])
            unique_results.append(r)
    
    print(f"[FRANIME] {len(unique_results)} source(s) video trouvee(s)")
    return unique_results
