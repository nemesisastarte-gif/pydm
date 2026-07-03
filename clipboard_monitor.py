"""
Module clipboard_monitor.py - Surveillance du presse-papiers.
Utilise xclip (Linux/X11) ou wl-paste (Wayland) pour détecter
les URLs copiées et les proposer au téléchargement.
Fonctionne sans dépendance Python externe.
"""

import subprocess
import time
import re
import threading
from urllib.parse import urlparse


# Patterns d'URLs considérées comme téléchargeables
DOWNLOAD_PATTERNS = [
    r'https?://.*\.(mp4|mkv|avi|mov|wmv|flv|webm)',
    r'https?://.*\.(zip|rar|7z|tar|gz|bz2|xz)',
    r'https?://.*\.(pdf|doc|docx|xls|xlsx|ppt|pptx)',
    r'https?://.*\.(exe|msi|deb|rpm|appimage)',
    r'https?://.*\.(iso|img|dmg)',
    r'https?://.*\.(torrent|magnet)',
    r'https?://drive\.google\.com/.*',
    r'https?://mega\.nz/.*',
    r'https?://mega\.co\.nz/.*',
    r'https?://mediafire\.com/.*',
    r'https?://dropbox\.com/.*',
    r'https?://.*franime\..*',
    r'https?://.*anime\..*',
    r'https?://.*/download/.*',
    r'https?://.*\.(mp3|flac|wav|ogg|aac)',
]


def get_clipboard_content() -> str:
    """
    Recupere le contenu du presse-papiers via xclip (X11)
    ou wl-paste (Wayland).
    """
    try:
        # Essayer xclip (X11)
        result = subprocess.run(
            ["xclip", "-selection", "clipboard", "-o"],
            capture_output=True, text=True, timeout=1
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    try:
        # Essayer wl-paste (Wayland)
        result = subprocess.run(
            ["wl-paste"],
            capture_output=True, text=True, timeout=1
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return ""


def is_download_url(text: str) -> bool:
    """
    Verifie si le texte correspond a une URL telechargeable.
    """
    if not text or len(text) > 2000:
        return False

    # Verifier que ca ressemble a une URL
    parsed = urlparse(text)
    if not parsed.scheme or not parsed.netloc:
        return False

    # Verifier les patterns connus
    for pattern in DOWNLOAD_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    return False


def extract_filename_from_url(url: str) -> str:
    """Extrait un nom de fichier probable depuis l'URL."""
    parsed = urlparse(url)
    path = parsed.path
    filename = path.split("/")[-1]
    if filename:
        # Nettoyer les parametres
        filename = filename.split("?")[0]
        return filename
    return "download.bin"


class ClipboardMonitor:
    """
    Surveille le presse-papiers en continu dans un thread separe.
    Quand une URL telechargeable est detectee, appelle le callback.
    """

    def __init__(self, callback=None, interval: float = 1.0):
        """
        Args:
            callback: Fonction appelee avec (url, filename) quand une URL
                      est detectee. Retourne True si l'URL est prise en charge.
            interval: Intervalle de verification en secondes.
        """
        self.callback = callback
        self.interval = interval
        self.last_content = ""
        self.running = False
        self.thread = None

    def start(self) -> None:
        """Demarre la surveillance en arriere-plan."""
        if self.running:
            return
        self.running = True
        self.last_content = get_clipboard_content()  # Ignorer le contenu actuel
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        print("[INFO] Surveillance du presse-papiers activee.")

    def stop(self) -> None:
        """Arrete la surveillance."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        print("[INFO] Surveillance du presse-papiers arretee.")

    def _monitor_loop(self) -> None:
        """Boucle principale de surveillance."""
        while self.running:
            try:
                current = get_clipboard_content()
                if current and current != self.last_content:
                    self.last_content = current
                    if is_download_url(current):
                        filename = extract_filename_from_url(current)
                        print(f"\n[CLIPBOARD] URL detectee : {current[:80]}...")
                        if self.callback:
                            accepted = self.callback(current, filename)
                            if accepted:
                                print("[CLIPBOARD] URL envoyee au gestionnaire.")
                            else:
                                print("[CLIPBOARD] URL ignoree.")
            except Exception:
                pass  # Eviter de planter la boucle

            time.sleep(self.interval)
