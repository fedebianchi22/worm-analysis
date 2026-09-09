"""
Estado de la sesión de trabajo. Ya no es una app multiusuario, así que en
vez de guardar todo solo en memoria (se perdía si el programa se cerraba
mal, se apagaba la PC, etc.) se persiste a un archivo en el disco después
de cada cambio, en una carpeta estable (no una temporal que se puede
borrar) — así, si el programa se cierra de golpe, al volver a abrirlo el
trabajo sigue ahí tal como había quedado.
"""
import json
import os
import secrets
import shutil
import time

from measure_worms import OBJETIVO_POR_DEFECTO

COOKIE_NAME = "celab_sesion"
TTL_SEGUNDOS = 6 * 60 * 60  # limpiar sesiones abandonadas después de 6 horas

CARPETA_DATOS = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "CElegansLab")
CARPETA_TRABAJO = os.path.join(CARPETA_DATOS, "trabajo_actual")
ARCHIVO_ESTADO = os.path.join(CARPETA_TRABAJO, "estado.json")

SESSIONS = {}


def _nueva_sesion():
    os.makedirs(CARPETA_TRABAJO, exist_ok=True)
    return {
        "carpeta": CARPETA_TRABAJO,
        "selecciones": {0: {"nombre": "Selección 1", "objetivo": OBJETIVO_POR_DEFECTO, "archivos": []}},
        "siguiente_sid": 1,
        "grupos": {},
        "siguiente_gid": 0,
        "resultado": None,
        "saltados_revision": set(),
        "ultimo_acceso": time.time(),
    }


def guardar_estado(sesion):
    """Vuelca la sesión actual al disco. Se llama después de cualquier
    cambio (ver _redirigir en server.py) — no hace falta acordarse de
    invocarla a mano en cada ruta nueva que se agregue."""
    try:
        os.makedirs(CARPETA_TRABAJO, exist_ok=True)
        datos = {
            "selecciones": sesion["selecciones"],
            "siguiente_sid": sesion["siguiente_sid"],
            "grupos": sesion["grupos"],
            "siguiente_gid": sesion["siguiente_gid"],
            "resultado": sesion["resultado"],
            "saltados_revision": sorted(list(sesion.get("saltados_revision") or [])),
        }
        tmp = ARCHIVO_ESTADO + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False)
        os.replace(tmp, ARCHIVO_ESTADO)  # escritura atómica: nunca deja el .json a medio escribir
    except OSError:
        pass  # si falla el guardado no debe tirar abajo la acción que lo disparó


def cargar_estado_guardado():
    """Devuelve la sesión guardada en disco, o None si no hay ninguna (o
    está corrupta)."""
    if not os.path.exists(ARCHIVO_ESTADO):
        return None
    try:
        with open(ARCHIVO_ESTADO, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    sesion = _nueva_sesion()
    sesion["selecciones"] = {int(k): v for k, v in datos.get("selecciones", {}).items()} or sesion["selecciones"]
    sesion["siguiente_sid"] = datos.get("siguiente_sid", sesion["siguiente_sid"])
    sesion["grupos"] = {int(k): v for k, v in datos.get("grupos", {}).items()}
    sesion["siguiente_gid"] = datos.get("siguiente_gid", 0)
    resultado = datos.get("resultado")
    if resultado:
        resultado["selecciones"] = {int(k): v for k, v in resultado["selecciones"].items()}
    sesion["resultado"] = resultado
    sesion["saltados_revision"] = {tuple(x) for x in datos.get("saltados_revision", [])}
    return sesion


def limpiar_trabajo_guardado():
    """Borra todo lo guardado (fotos, resultados, el .json) para arrancar
    de cero — libera el espacio en disco que iba ocupando el trabajo
    anterior. Se usa cuando el usuario elige explícitamente empezar de
    nuevo, nunca automáticamente."""
    shutil.rmtree(CARPETA_TRABAJO, ignore_errors=True)
    os.makedirs(CARPETA_TRABAJO, exist_ok=True)


def reiniciar_sesion():
    """Vacía el trabajo guardado y devuelve una sesión nueva y vacía."""
    limpiar_trabajo_guardado()
    return _nueva_sesion()


def _purgar_viejas():
    limite = time.time() - TTL_SEGUNDOS
    for sid in [s for s, datos in SESSIONS.items() if datos["ultimo_acceso"] < limite]:
        SESSIONS.pop(sid, None)


def obtener_sesion(cookie_id):
    _purgar_viejas()
    if cookie_id and cookie_id in SESSIONS:
        SESSIONS[cookie_id]["ultimo_acceso"] = time.time()
        return cookie_id, SESSIONS[cookie_id]
    # Sesión nueva en memoria (pasa en cada arranque del programa, ya que
    # el diccionario SESSIONS vive solo mientras el proceso está corriendo)
    # -- si había trabajo guardado de la vez anterior, se recupera solo acá,
    # así el usuario no tiene que hacer nada para retomar donde había quedado.
    nuevo_id = secrets.token_urlsafe(24)
    SESSIONS[nuevo_id] = cargar_estado_guardado() or _nueva_sesion()
    return nuevo_id, SESSIONS[nuevo_id]
