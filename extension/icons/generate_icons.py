#!/usr/bin/env python3
"""
Génère des icônes PNG pour PyDM Bridge.
Fond sombre avec un éclair vert (symbole téléchargement rapide).
"""

import struct
import zlib
import math


def create_png(width, height, pixels):
    """
    Crée un PNG à partir d'une liste de pixels (R, G, B).
    pixels est une liste de height lignes, chaque ligne a width tuples (R, G, B).
    """
    def chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc
    
    signature = b'\x89PNG\r\n\x1a\n'
    
    # IHDR : 8 bits par canal, RGB
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr = chunk(b'IHDR', ihdr_data)
    
    # IDAT
    raw_data = b''
    for row in pixels:
        raw_data += b'\x00'  # Filtre None
        for r, g, b in row:
            raw_data += struct.pack("BBB", r, g, b)
    
    compressed = zlib.compress(raw_data)
    idat = chunk(b'IDAT', compressed)
    
    # IEND
    iend = chunk(b'IEND', b'')
    
    return signature + ihdr + idat + iend


def draw_icon(size):
    """
    Dessine un logo PyDM :
    - Fond arrondi sombre
    - Flèche vers le bas (téléchargement)
    - Éclair au centre (vitesse)
    Couleurs : fond #1a1a2e, accent #00d4aa
    """
    bg = (26, 26, 46)       # Fond sombre
    accent = (0, 212, 170)  # Vert PyDM
    accent_clair = (50, 230, 190)
    blanc = (220, 220, 220)
    
    pixels = []
    cx, cy = size / 2, size / 2
    radius = size / 2 - 2
    
    for y in range(size):
        row = []
        for x in range(size):
            # Distance au centre
            dx, dy = x - cx, y - cy
            dist = math.sqrt(dx * dx + dy * dy)
            
            # Arrondi des coins (cercle)
            if dist > radius:
                row.append((0, 0, 0))  # Transparent simulé par noir
                continue
            
            # Fond de base
            r, g, b = bg
            
            # Bordure du cercle
            if dist > radius - 2:
                r, g, b = (40, 40, 60)
            
            # Flèche de téléchargement (↓)
            arrow_top = cy - size * 0.25
            arrow_bottom = cy + size * 0.3
            arrow_width = size * 0.22
            
            # Corps de la flèche (rectangle vertical)
            if abs(dx) < size * 0.08 and arrow_top < dy < arrow_bottom:
                r, g, b = accent
            
            # Pointe de la flèche (triangle)
            if arrow_bottom - size * 0.2 < dy <= arrow_bottom + size * 0.1:
                progress = (dy - (arrow_bottom - size * 0.2)) / (size * 0.3)
                half_width = arrow_width * (1 - progress)
                if abs(dx) < half_width and dy > arrow_bottom - size * 0.15:
                    r, g, b = accent
            
            # Barre horizontale en haut de la flèche
            if abs(dy - arrow_top) < size * 0.06 and abs(dx) < size * 0.2:
                r, g, b = accent
            
            # Petit éclair au centre
            if size >= 48:
                lightning_x = cx
                lightning_y = cy
                if abs(dx) < size * 0.04 and abs(dy) < size * 0.15:
                    # Vérifier que c'est dans la zone de l'éclair (forme zigzag)
                    ly = abs(dy)
                    lx = abs(dx)
                    if lx < size * 0.03 + ly * 0.3:
                        r, g, b = blanc
            
            # Point brillant en haut à gauche
            if dist < radius * 0.3 and dx < -size * 0.15 and dy < -size * 0.15:
                r = min(255, r + 40)
                g = min(255, g + 40)
                b = min(255, b + 40)
            
            row.append((r, g, b))
        pixels.append(row)
    
    return create_png(size, size, pixels)


for size in [16, 48, 128]:
    png_data = draw_icon(size)
    with open(f"icon{size}.png", "wb") as f:
        f.write(png_data)
    print(f"icon{size}.png généré ({size}x{size})")

print("Icônes prêtes.")
