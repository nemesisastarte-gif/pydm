"""
Module segment_downloader.py - Telecharge une plage d'octets specifique.
Chaque instance tourne dans un thread separe et ecrit dans un fichier
temporaire (.partN). La progression est envoyee via une queue thread-safe.
"""

import requests
import os
import time
from queue import Queue


def download_segment(url: str,
                     start_byte: int,
                     end_byte: int,
                     segment_id: int,
                     part_filepath: str,
                     progress_queue: Queue,
                     retries: int = 3,
                     cookies: dict = None,
                     extra_headers: dict = None) -> None:
    """
    Telecharge une plage d'octets [start_byte, end_byte] et l'ecrit
    dans le fichier temporaire part_filepath.

    Args:
        url: L'URL du fichier a telecharger.
        start_byte: Premier octet de la plage (inclus).
        end_byte: Dernier octet de la plage (inclus).
        segment_id: Identifiant unique du segment (0, 1, 2...).
        part_filepath: Chemin complet du fichier .partN.
        progress_queue: Queue partagee pour envoyer les mises a jour
                        de progression sous forme (segment_id, octets_ajoutes).
        retries: Nombre de tentatives en cas d'echec reseau.
        cookies: Cookies optionnels.
        extra_headers: Headers HTTP supplementaires.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Range": f"bytes={start_byte}-{end_byte}"
    }
    
    if extra_headers:
        headers.update(extra_headers)

    # Verifier si le fichier partiel existe deja (pour reprise)
    existing_size = 0
    if os.path.exists(part_filepath):
        existing_size = os.path.getsize(part_filepath)
        if existing_size > 0:
            new_start = start_byte + existing_size
            if new_start <= end_byte:
                headers["Range"] = f"bytes={new_start}-{end_byte}"
                start_byte = new_start
            else:
                progress_queue.put((segment_id, 0, True))
                return

    attempt = 0
    while attempt < retries:
        try:
            response = requests.get(
                url, headers=headers, cookies=cookies,
                stream=True, timeout=60
            )
            response.raise_for_status()

            with open(part_filepath, "ab") as part_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        part_file.write(chunk)
                        progress_queue.put((segment_id, len(chunk), False))

            progress_queue.put((segment_id, 0, True))
            return

        except (requests.exceptions.RequestException, IOError) as e:
            attempt += 1
            print(f"[ATTENTION] Segment {segment_id} - Tentative {attempt}/{retries} echouee : {e}")
            if attempt < retries:
                time.sleep(2)

    print(f"[ERREUR] Segment {segment_id} - Echec definitif apres {retries} tentatives.")
    progress_queue.put((segment_id, -1, True))
