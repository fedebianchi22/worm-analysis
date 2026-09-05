"""Genera el ícono de la app (assets/icon.ico) a partir de formas simples,
sin depender de ningún archivo de imagen externo. Se corre una sola vez;
el resultado se commitea al repo."""
import math
import os

from PIL import Image, ImageDraw

TAMANO = 256
FONDO = (124, 79, 224, 255)   # --accent
FONDO_2 = (99, 54, 200, 255)  # --accent-strong (para el borde/sombra sutil)
GUSANO = (255, 255, 255, 255)


def _rounded_square(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def generar():
    img = Image.new("RGBA", (TAMANO, TAMANO), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margen = 8
    _rounded_square(draw, (margen, margen, TAMANO - margen, TAMANO - margen), radius=56, fill=FONDO)

    # Gusano: una curva en S gruesa (como un nematodo visto al
    # microscopio), en blanco sobre el fondo violeta. Se "estampa" con
    # muchos círculos superpuestos en vez de una polilínea, para que no
    # queden artefactos de anti-aliasing en las uniones.
    grosor = 30
    r = grosor / 2
    x0, x1 = 62, 194
    muestras = 200
    for i in range(muestras + 1):
        t = i / muestras
        x = x0 + (x1 - x0) * t
        y = 128 + 52 * math.sin(t * math.pi * 1.6) * (1 - 0.15 * t)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=GUSANO)

    salida_png = os.path.join(os.path.dirname(__file__), "icon_preview.png")
    img.save(salida_png)

    salida_ico = os.path.join(os.path.dirname(__file__), "icon.ico")
    img.save(salida_ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("Generado:", salida_png, "y", salida_ico)


if __name__ == "__main__":
    generar()
