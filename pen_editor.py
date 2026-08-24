"""
Editor de contorno estilo "pluma" (Photoshop): click en la línea para agregar
un punto, arrastrar un punto mueve la línea en vivo, y click en un punto
(sin arrastrar) muestra un menú para eliminarlo o activar curva suave.
Componente propio en pen_editor/index.html (sin dependencias externas).
"""
import os
import streamlit.components.v1 as components

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pen_editor")
_component = components.declare_component("pen_editor", path=_DIR)


def pen_editor(image_data_uri, width, height, points, smooth=False, key=None):
    """
    image_data_uri: imagen de fondo como data: URI.
    width, height: tamaño del canvas en px.
    points: lista inicial de [x, y] en coordenadas del canvas.
    Devuelve {"points": [[x,y], ...], "smooth": bool} con el estado actual
    (se actualiza en cada edición del usuario).
    """
    default = {"points": [[float(x), float(y)] for x, y in points], "smooth": smooth}
    resultado = _component(
        image=image_data_uri,
        width=width,
        height=height,
        points=[[float(x), float(y)] for x, y in points],
        smooth=smooth,
        key=key,
        default=default,
    )
    return resultado or default
