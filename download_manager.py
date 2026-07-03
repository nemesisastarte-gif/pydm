"""
Module download_manager.py - Chef d'orchestre du téléchargement.
Coordonne l'interrogation du serveur, le découpage en segments,
le lancement parallèle des téléchargeurs et l'assemblage final.
"""

import os
import time
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
from threading import Lock

from http_utils import get_file_info
from segment_downloader import download_segment
from config import save_state, load_state, clear_state


class DownloadManager:
    """Gère l'intégralité d'un téléchargement segmenté."""

    def __init__(self):
        self.progress_queue = Queue()
        self.lock = Lock()
        self.total_downloaded = 0
        self.segment_done = {}

    def _progress_monitor(self, total_size: int, num_segments: int) -> None:
        """
        Surveille la queue de progression et met à jour l'affichage global.
        """
        segments_completed = 0
        start_time = time.time()

        while segments_completed < num_segments:
            try:
                seg_id, added_bytes, is_done = self.progress_queue.get(timeout=0.5)

                if added_bytes == -1:
                    # Erreur sur un segment
                    print(f"\n[ERREUR] Le segment {seg_id} a échoué définitivement.")
                    return

                with self.lock:
                    self.total_downloaded += added_bytes

                if is_done:
                    segments_completed += 1
                    self.segment_done[seg_id] = True

                # Calcul de la progression
                pct = (self.total_downloaded / total_size) * 100
                elapsed = time.time() - start_time
                speed = self.total_downloaded / elapsed if elapsed > 0 else 0
                speed_str = self._format_speed(speed)

                # Barre de progression ASCII
                bar_length = 30
                filled = int(bar_length * self.total_downloaded // total_size)
                bar = "█" * filled + "░" * (bar_length - filled)

                print(f"\r[{bar}] {pct:.1f}% | {self._format_size(self.total_downloaded)}/"
                      f"{self._format_size(total_size)} | {speed_str} | Segments: {segments_completed}/{num_segments}",
                      end="", flush=True)

            except Exception:
                pass

        print()  # Saut de ligne final

    def start_download(self,
                       url: str,
                       filename: str = None,
                       num_segments: int = 4,
                       resume: bool = True,
                       cookies: dict = None,
                       extra_headers: dict = None) -> bool:
        """
        Lance le telechargement complet.

        Args:
            url: URL du fichier.
            filename: Nom du fichier de sortie (deduit de l'URL si None).
            num_segments: Nombre de segments paralleles.
            resume: Tenter de reprendre un telechargement interrompu.
            cookies: Cookies a transmettre.
            extra_headers: Headers HTTP supplementaires.

        Returns:
            bool: True si succes, False sinon.
        """
        # Deduire le nom du fichier depuis l'URL si non fourni
        if filename is None:
            filename = url.split("/")[-1].split("?")[0]
            if not filename:
                filename = "download.bin"

        print(f"[INFO] Telechargement : {url}")
        print(f"[INFO] Fichier de sortie : {filename}")
        print(f"[INFO] Nombre de segments : {num_segments}")

        # Etape 1 : Obtenir les infos du fichier
        print("[INFO] Interrogation du serveur...")
        file_size, supports_resume = get_file_info(url, cookies=cookies, extra_headers=extra_headers)

        if file_size is None:
            print("[ERREUR] Impossible de déterminer la taille du fichier.")
            return False

        if not supports_resume:
            print("[ATTENTION] Le serveur ne supporte pas le téléchargement par plages.")
            print("[INFO] Passage en téléchargement simple (1 segment).")
            num_segments = 1

        print(f"[INFO] Taille du fichier : {self._format_size(file_size)}")

        # Étape 2 : Calculer les plages pour chaque segment
        segment_size = math.ceil(file_size / num_segments)
        segments = []
        for i in range(num_segments):
            start = i * segment_size
            end = min(start + segment_size - 1, file_size - 1)
            if start <= end:
                segments.append((start, end))

        num_segments = len(segments)

        # Étape 3 : Préparer les fichiers temporaires
        part_files = []
        for i in range(num_segments):
            part_file = f"{filename}.part{i}"
            part_files.append(part_file)

        # Étape 4 : Reprise ?
        if resume:
            saved_state = load_state()
            if saved_state and saved_state.get("url") == url:
                print("[INFO] État précédent trouvé, reprise du téléchargement...")
                for i, part_file in enumerate(part_files):
                    if os.path.exists(part_file):
                        downloaded = os.path.getsize(part_file)
                        print(f"  Segment {i}: {self._format_size(downloaded)} déjà téléchargés")
                        with self.lock:
                            self.total_downloaded += downloaded

        # Étape 5 : Sauvegarder l'état initial
        save_state(url, filename, file_size, num_segments, part_files)

        # Étape 6 : Lancer les threads
        print("[INFO] Démarrage du téléchargement...")
        with ThreadPoolExecutor(max_workers=num_segments) as executor:
            futures = []
            for i, (start, end) in enumerate(segments):
                future = executor.submit(
                    download_segment,
                    url, start, end, i, part_files[i], self.progress_queue, 3, cookies, extra_headers
                )
                futures.append(future)

            # Lancer le moniteur de progression dans le thread principal
            self._progress_monitor(file_size, num_segments)

            # Vérifier les erreurs
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"[ERREUR] Exception dans un thread : {e}")
                    return False

        # Étape 7 : Assembler les fichiers
        print("[INFO] Assemblage des segments...")
        success = self._assemble_file(filename, part_files)

        if success:
            print(f"[SUCCÈS] Téléchargement terminé : {filename}")
            clear_state()
        else:
            print("[ERREUR] L'assemblage a échoué.")
            return False

        return True

    def _assemble_file(self, output_filename: str, part_files: list) -> bool:
        """
        Fusionne tous les fichiers .partN dans le fichier final,
        puis supprime les fichiers temporaires.
        """
        try:
            with open(output_filename, "wb") as outfile:
                for part_file in part_files:
                    if not os.path.exists(part_file):
                        print(f"[ERREUR] Fichier segment manquant : {part_file}")
                        return False
                    with open(part_file, "rb") as infile:
                        while True:
                            chunk = infile.read(8192)
                            if not chunk:
                                break
                            outfile.write(chunk)

            # Suppression des fichiers temporaires
            for part_file in part_files:
                if os.path.exists(part_file):
                    os.remove(part_file)

            return True

        except IOError as e:
            print(f"[ERREUR] Erreur lors de l'assemblage : {e}")
            return False

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Convertit des octets en format lisible (Ko, Mo, Go)."""
        for unit in ["o", "Ko", "Mo", "Go", "To"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} Po"

    @staticmethod
    def _format_speed(speed_bytes: float) -> str:
        """Convertit une vitesse en format lisible."""
        return DownloadManager._format_size(int(speed_bytes)) + "/s"
