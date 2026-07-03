#!/usr/bin/env python3
"""
PyDM - Python Download Manager
Un gestionnaire de téléchargements avec segmentation et parallélisation,
inspiré d'IDM, fonctionnant sous Linux.

Commandes:
    download <url>        Lancer un téléchargement direct
    resume                Reprendre le dernier téléchargement interrompu
    clean                 Nettoyer les fichiers temporaires et l'état
    interactive           Mode interactif pas-à-pas
    clipboard             Surveiller le presse-papiers (URLs detectees)
    ws-server             Démarrer le serveur WebSocket pour extension navigateur
    drive <url>           Resoudre une URL Google Drive
    franime <url>         Extraire les URLs vidéo d'une page Franime

Exemples:
    python main.py download "http://exemple.com/fichier.zip"
    python main.py download "http://exemple.com/fichier.zip" -n 8
    python main.py interactive
    python main.py clipboard
    python main.py drive "https://drive.google.com/file/d/xxx/view"
    python main.py franime "https://franime.fr/episode/xxx"
"""

import argparse
import sys
import os
import signal
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from download_manager import DownloadManager
from config import load_state, clear_state
from drive_handler import is_google_drive_url, resolve_drive_url
from franime_handler import is_franime_url, resolve_franime_page


def cmd_download(args):
    """Lance un nouveau téléchargement."""
    url = args.url
    
    # Si c'est une URL Google Drive, la resoudre d'abord
    if is_google_drive_url(url):
        print("[INFO] URL Google Drive détectée, résolution...")
        resolved = resolve_drive_url(url)
        if resolved:
            url = resolved["direct_url"]
            if not args.output:
                args.output = resolved.get("filename")
            print(f"[INFO] URL résolue : {url}")
        else:
            print("[ERREUR] Impossible de résoudre l'URL Google Drive.")
            sys.exit(1)
    
    # Si c'est une URL Franime, extraire les vidéos
    if is_franime_url(url):
        print("[INFO] URL Franime détectée, extraction des vidéos...")
        videos = resolve_franime_page(url)
        if videos:
            print(f"\n[INFO] {len(videos)} vidéo(s) trouvée(s) :")
            for i, v in enumerate(videos):
                print(f"  [{i+1}] {v['host']}: {v['filename']}")
            
            choice = input("\nNuméro de la vidéo à télécharger (1, 2, ...) ou 'q': ").strip()
            if choice.lower() == 'q':
                sys.exit(0)
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(videos):
                    url = videos[idx]["direct_url"]
                    if not args.output:
                        args.output = videos[idx]["filename"]
                else:
                    print("[ERREUR] Numéro invalide.")
                    sys.exit(1)
            except ValueError:
                print("[ERREUR] Entrée invalide.")
                sys.exit(1)
        else:
            print("[ERREUR] Aucune vidéo trouvée.")
            sys.exit(1)
    
    manager = DownloadManager()
    success = manager.start_download(
        url=url,
        filename=args.output,
        num_segments=args.segments,
        resume=not args.no_resume
    )
    if not success:
        print("[INFO] État sauvegardé. Utilisez 'python main.py resume' pour réessayer.")
        sys.exit(1)


def cmd_resume(args):
    """Reprend le dernier téléchargement interrompu."""
    state = load_state()
    if state is None:
        print("[INFO] Aucun téléchargement à reprendre.")
        return

    print(f"[INFO] Reprise du téléchargement de : {state['filename']}")
    manager = DownloadManager()
    manager.total_downloaded = sum(state.get("segment_progress", {}).values())
    success = manager.start_download(
        url=state["url"],
        filename=state["filename"],
        num_segments=state["num_segments"],
        resume=True
    )
    if not success:
        print("[INFO] État sauvegardé. Réessayez avec 'python main.py resume'.")
        sys.exit(1)


def cmd_clean(args):
    """Supprime l'état et les fichiers temporaires d'un téléchargement interrompu."""
    state = load_state()
    if state:
        for part_file in state.get("segment_files", []):
            if os.path.exists(part_file):
                os.remove(part_file)
                print(f"[INFO] Supprimé : {part_file}")
        clear_state()
        print("[INFO] Nettoyage terminé.")
    else:
        print("[INFO] Rien à nettoyer.")


def cmd_interactive(args):
    """Mode interactif pas-à-pas."""
    print("""
╔══════════════════════════════════════════════════╗
║        PyDM - Mode Interactif Pas-à-Pas          ║
╚══════════════════════════════════════════════════╝
    """)
    
    url = _prompt_step("Étape 1/5 - URL du fichier",
                       "Entrez l'URL complète du fichier\n> ", required=True)
    if url is None: return
    
    # Résolution Drive/Franime automatique
    if is_google_drive_url(url):
        print("[INFO] URL Google Drive détectée, résolution...")
        resolved = resolve_drive_url(url)
        if resolved:
            url = resolved["direct_url"]
            print(f"[INFO] URL résolue : {url}")
    elif is_franime_url(url):
        print("[INFO] URL Franime détectée, extraction...")
        videos = resolve_franime_page(url)
        if videos:
            for i, v in enumerate(videos):
                print(f"  [{i+1}] {v['host']}: {v['filename']}")
            choice = input("Numéro: ").strip()
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(videos):
                    url = videos[idx]["direct_url"]
            except ValueError:
                pass
    
    default_name = url.split("/")[-1].split("?")[0] or "download.bin"
    filename = _prompt_step("Étape 2/5 - Nom du fichier",
                            f"Nom (vide = '{default_name}')\n> ", required=False)
    if filename is None: return
    if not filename.strip(): filename = default_name
    
    segments_str = _prompt_step("Étape 3/5 - Segments",
                                "Nombre de segments (défaut: 4)\n> ", required=False)
    if segments_str is None: return
    try: num_segments = int(segments_str) if segments_str.strip() else 4
    except ValueError: num_segments = 4
    if num_segments < 1 or num_segments > 32: num_segments = 4
    
    state = load_state()
    use_resume = False
    if state and state.get("url") == url:
        r = _prompt_step("Étape 4/5 - Reprise",
                         "Reprendre le téléchargement précédent ? (o/n)\n> ", required=False)
        if r is None: return
        use_resume = r.strip().lower() != "n"
    
    confirm = _prompt_step("Étape 5/5 - Confirmation",
                           "Lancer ? (o/n)\n> ", required=False)
    if confirm is None or confirm.strip().lower() == "n":
        print("[INFO] Annulé.")
        return
    
    manager = DownloadManager()
    if use_resume:
        manager.total_downloaded = sum(state.get("segment_progress", {}).values())
    
    success = manager.start_download(
        url=url, filename=filename,
        num_segments=num_segments, resume=use_resume
    )
    if not success:
        print("[INFO] État sauvegardé. Utilisez 'resume' pour réessayer.")
        sys.exit(1)


def cmd_clipboard(args):
    """Surveille le presse-papiers pour détecter les URLs."""
    from clipboard_monitor import ClipboardMonitor
    
    def on_url_detected(url, filename):
        print(f"\n[CLIPBOARD] Voulez-vous télécharger : {filename} ?")
        choice = input("  (o/n/q pour quitter) : ").strip().lower()
        if choice == 'q':
            return False  # Arrêter la surveillance
        if choice == 'o' or choice == '':
            print(f"[CLIPBOARD] Lancement du téléchargement : {filename}")
            manager = DownloadManager()
            manager.start_download(url=url, filename=filename, num_segments=4)
        return True
    
    monitor = ClipboardMonitor(callback=on_url_detected, interval=1.0)
    monitor.start()
    
    print("[INFO] Surveillance du presse-papiers en cours... (Ctrl+C pour arrêter)")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[INFO] Arrêt demandé.")
    finally:
        monitor.stop()


def cmd_ws_server(args):
    """Démarre le serveur WebSocket pour l'extension navigateur."""
    from websocket_server import SimpleWebSocketServer
    def on_message(data):
        print(f"\n[WS] Message recu : {data}")
        if data.get("action") == "download":
            url = data.get("url", "")
            filename = data.get("filename", "download.bin")
            file_size = data.get("fileSize", 0)
            cookies = data.get("cookies", {})
            referer = data.get("referer", "")
            print(f"[WS] Telechargement demande : {filename} ({file_size} octets)")
            choice = input("  Lancer le telechargement ? (o/n) : ").strip().lower()
            if choice == 'o' or choice == '':
                manager = DownloadManager()
                extra_headers = {"Referer": referer} if referer else {}
                manager.start_download(url=url, filename=filename, num_segments=4, cookies=cookies, extra_headers=extra_headers)
    
    server = SimpleWebSocketServer(host="127.0.0.1", port=9090)
    server.set_callback(on_message)
    server.start()
    
    print("[INFO] Serveur WebSocket en écoute sur ws://127.0.0.1:9090")
    print("[INFO] Installez l'extension navigateur pour connecter votre butineur.")
    print("[INFO] Ctrl+C pour arrêter.")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[INFO] Arrêt demandé.")
    finally:
        server.stop()


def cmd_drive(args):
    """Résout une URL Google Drive et lance le téléchargement."""
    url = args.url
    print(f"[INFO] Résolution de l'URL Google Drive : {url}")
    resolved = resolve_drive_url(url)
    
    if not resolved:
        print("[ERREUR] Impossible de résoudre l'URL Google Drive.")
        sys.exit(1)
    
    print(f"\nRésultat :")
    print(f"  URL directe : {resolved['direct_url']}")
    print(f"  Nom         : {resolved['filename']}")
    print(f"  Taille      : {resolved.get('size', 'Inconnue')}")
    
    if args.download:
        print("\n[INFO] Lancement du téléchargement...")
        manager = DownloadManager()
        success = manager.start_download(
            url=resolved["direct_url"],
            filename=resolved["filename"],
            num_segments=args.segments
        )
        if not success:
            sys.exit(1)


def cmd_franime(args):
    """Extrait les URLs vidéo d'une page Franime."""
    url = args.url
    print(f"[INFO] Analyse de la page Franime : {url}")
    videos = resolve_franime_page(url)
    
    if not videos:
        print("[INFO] Aucune vidéo trouvée.")
        return
    
    print(f"\n{len(videos)} vidéo(s) trouvée(s) :")
    for i, v in enumerate(videos):
        print(f"  [{i+1}] {v['host']:15s} | {v['filename']}")
    
    if args.download:
        choice = input(f"\nNuméro (1-{len(videos)}) ou 'q' : ").strip()
        if choice.lower() == 'q':
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(videos):
                v = videos[idx]
                manager = DownloadManager()
                manager.start_download(
                    url=v["direct_url"],
                    filename=v["filename"],
                    num_segments=args.segments
                )
        except (ValueError, IndexError):
            print("[ERREUR] Numéro invalide.")


def _prompt_step(title: str, message: str, required: bool = False):
    """Affiche une étape et attend la saisie utilisateur."""
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")
    print(message, end="")
    sys.stdout.flush()
    
    while True:
        user_input = input().strip()
        if user_input.lower() == "q":
            print("[INFO] Quitté.")
            return None
        if required and not user_input:
            print("Obligatoire. Réessayez ou 'q'.")
            print("> ", end="")
            sys.stdout.flush()
            continue
        return user_input


def main():
    parser = argparse.ArgumentParser(
        description="PyDM - Python Download Manager (inspiré d'IDM pour Linux)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  %(prog)s download "http://exemple.com/fichier.zip"
  %(prog)s download "http://exemple.com/fichier.zip" -n 8
  %(prog)s resume
  %(prog)s clean
  %(prog)s interactive
  %(prog)s clipboard
  %(prog)s drive "https://drive.google.com/file/d/xxx/view" --download
  %(prog)s franime "https://franime.fr/episode/xxx" --download
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commandes disponibles")
    
    # download
    p = subparsers.add_parser("download", help="Lancer un nouveau téléchargement")
    p.add_argument("url", help="URL du fichier à télécharger")
    p.add_argument("-n", "--segments", type=int, default=4)
    p.add_argument("-o", "--output", type=str, default=None)
    p.add_argument("--no-resume", action="store_true")
    p.set_defaults(func=cmd_download)
    
    # resume
    p = subparsers.add_parser("resume", help="Reprendre le dernier téléchargement interrompu")
    p.set_defaults(func=cmd_resume)
    
    # clean
    p = subparsers.add_parser("clean", help="Nettoyer les fichiers temporaires")
    p.set_defaults(func=cmd_clean)
    
    # interactive
    p = subparsers.add_parser("interactive", help="Mode interactif pas-à-pas")
    p.set_defaults(func=cmd_interactive)
    
    # clipboard
    p = subparsers.add_parser("clipboard", help="Surveiller le presse-papiers")
    p.set_defaults(func=cmd_clipboard)
    
    # ws-server
    p = subparsers.add_parser("ws-server", help="Démarrer le serveur WebSocket")
    p.set_defaults(func=cmd_ws_server)
    
    # drive
    p = subparsers.add_parser("drive", help="Résoudre une URL Google Drive")
    p.add_argument("url", help="URL Google Drive")
    p.add_argument("--download", action="store_true", help="Lancer le téléchargement après résolution")
    p.add_argument("-n", "--segments", type=int, default=4)
    p.set_defaults(func=cmd_drive)
    
    # franime
    p = subparsers.add_parser("franime", help="Extraire les URLs vidéo d'une page Franime")
    p.add_argument("url", help="URL Franime")
    p.add_argument("--download", action="store_true", help="Lancer le téléchargement après extraction")
    p.add_argument("-n", "--segments", type=int, default=4)
    p.set_defaults(func=cmd_franime)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(0)
    
    args.func(args)


if __name__ == "__main__":
    main()
