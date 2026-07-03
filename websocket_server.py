"""
Module websocket_server.py - Serveur WebSocket local simplifie.
Permet a une extension navigateur d'envoyer des URLs a PyDM.
Implemente le protocole WebSocket (RFC 6455) en version minimale.
Aucune dependance externe.
"""

import socket
import hashlib
import base64
import struct
import json
import threading
from typing import Optional, Callable


class SimpleWebSocketServer:
    """
    Serveur WebSocket minimaliste pour recevoir des commandes
    depuis une extension de navigateur.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9090):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.clients: list[socket.socket] = []
        self.callback: Optional[Callable] = None

    def set_callback(self, callback: Callable) -> None:
        """
        Definit la fonction appelee quand un message est recu.
        callback(data: dict) -> None
        """
        self.callback = callback

    def start(self) -> None:
        """Demarre le serveur WebSocket en arriere-plan."""
        if self.running:
            return
        self.running = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(5)
        self.socket.settimeout(1.0)

        self.thread = threading.Thread(target=self._accept_loop, daemon=True)
        self.thread.start()
        print(f"[WS] Serveur WebSocket demarre sur ws://{self.host}:{self.port}")

    def stop(self) -> None:
        """Arrete le serveur WebSocket."""
        self.running = False
        for client in self.clients:
            try:
                client.close()
            except Exception:
                pass
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
        print("[WS] Serveur WebSocket arrete.")

    def _accept_loop(self) -> None:
        """Boucle d'acceptation des connexions."""
        while self.running:
            try:
                client, addr = self.socket.accept()
                print(f"[WS] Nouvelle connexion : {addr}")
                self.clients.append(client)
                threading.Thread(
                    target=self._handle_client,
                    args=(client,),
                    daemon=True
                ).start()
            except socket.timeout:
                continue
            except Exception:
                if self.running:
                    continue

    def _handle_client(self, client: socket.socket) -> None:
        """Gere un client WebSocket : handshake puis reception de messages."""
        try:
            # Lire la requete HTTP d'upgrade
            data = client.recv(4096).decode("utf-8", errors="ignore")
            if "Upgrade: websocket" not in data:
                client.close()
                return

            # Extraire la cle WebSocket
            key = None
            for line in data.split("\r\n"):
                if line.lower().startswith("sec-websocket-key:"):
                    key = line.split(":", 1)[1].strip()
                    break

            if not key:
                client.close()
                return

            # Calculer la reponse d'acceptation
            magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
            accept = base64.b64encode(
                hashlib.sha1((key + magic).encode()).digest()
            ).decode()

            # Envoyer la reponse HTTP 101 Switching Protocols
            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n"
                "\r\n"
            )
            client.send(response.encode())

            # Boucle de reception des trames WebSocket
            while self.running:
                frame = self._recv_frame(client)
                if frame is None:
                    break

                opcode, payload = frame
                if opcode == 0x8:  # Close frame
                    break
                if opcode == 0x1:  # Text frame
                    try:
                        message = json.loads(payload)
                        print(f"[WS] Message recu : {message}")
                        if self.callback:
                            self.callback(message)
                    except json.JSONDecodeError:
                        print(f"[WS] Message non-JSON ignore : {payload[:100]}")

        except Exception as e:
            print(f"[WS] Erreur client : {e}")
        finally:
            try:
                client.close()
            except Exception:
                pass
            if client in self.clients:
                self.clients.remove(client)

    def _recv_frame(self, client: socket.socket):
        """
        Lit une trame WebSocket complete.
        Retourne (opcode, payload) ou None si erreur.
        """
        try:
            # Lire les 2 premiers octets
            header = client.recv(2)
            if len(header) < 2:
                return None

            opcode = header[0] & 0x0F
            masked = (header[1] & 0x80) != 0
            length = header[1] & 0x7F

            # Gerer les longueurs etendues
            if length == 126:
                ext = client.recv(2)
                if len(ext) < 2:
                    return None
                length = struct.unpack("!H", ext)[0]
            elif length == 127:
                ext = client.recv(8)
                if len(ext) < 8:
                    return None
                length = struct.unpack("!Q", ext)[0]

            # Lire le masque si present
            if masked:
                mask = client.recv(4)
                if len(mask) < 4:
                    return None

            # Lire le payload
            payload = b""
            while len(payload) < length:
                chunk = client.recv(min(length - len(payload), 4096))
                if not chunk:
                    return None
                payload += chunk

            # Demasquer si necessaire
            if masked:
                payload = bytes(
                    payload[i] ^ mask[i % 4] for i in range(len(payload))
                )

            return opcode, payload.decode("utf-8", errors="ignore")

        except Exception:
            return None
