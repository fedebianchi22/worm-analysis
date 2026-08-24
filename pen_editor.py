"""
Editor de contorno estilo "pluma" (Photoshop): click en la línea para agregar
un punto, arrastrar un punto mueve la línea en vivo, y click en un punto (sin
arrastrar) muestra un menú para eliminarlo o convertirlo en punto curvo (con
manijas de curvatura propias, como en Illustrator/Photoshop). Componente
propio en pen_editor/index.html, sin dependencias externas.
"""
import os
import streamlit.components.v1 as components

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pen_editor")
_component = components.declare_component("pen_editor", path=_DIR)


def pen_editor(image_data_uri, width, height, points, key=None):
    """
    image_data_uri: imagen de fondo como data: URI.
    width, height: tamaño del canvas en px.
    points: lista inicial de puntos, cada uno un dict con "x", "y" y
        opcionalmente "curved" (bool), "hx"/"hy" (offset de la manija de
        curvatura respecto al punto; 0,0 = esquina recta).
    Devuelve {"points": [{"x","y","curved","hx","hy"}, ...]} con el estado
    actual (se actualiza en cada edición del usuario).
    """
    puntos_norm = [
        {
            "x": float(p["x"]), "y": float(p["y"]),
            "curved": bool(p.get("curved", False)),
            "hx": float(p.get("hx", 0)), "hy": float(p.get("hy", 0)),
        }
        for p in points
    ]
    default = {"points": puntos_norm}
    resultado = _component(
        image=image_data_uri,
        width=width,
        height=height,
        points=puntos_norm,
        key=key,
        default=default,
    )
    return resultado or default
