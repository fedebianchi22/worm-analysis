"""
Estado en memoria por sesión de navegador (una cookie por visitante, sin base
de datos: alcanza para el uso del laboratorio y evita depender de nada
externo). Cada sesión tiene sus propias selecciones, grupos y resultados.
"""
import secrets
import tempfile
import time

from measure_worms import OBJETIVO_POR_DEFECTO

COOKIE_NAME = "celab_sesion"
TTL_SEGUNDOS = 6 * 60 * 60  # limpiar sesiones abandonadas después de 6 horas

SESSIONS = {}


def _nueva_sesion():
    return {
        "carpeta": tempfile.mkdtemp(prefix="celab_sesion_"),
        "selecciones": {0: {"nombre": "Selección 1", "objetivo": OBJETIVO_POR_DEFECTO, "archivos": []}},
        "siguiente_sid": 1,
        "grupos": {},
        "siguiente_gid": 0,
        "resultado": None,
        "ultimo_acceso": time.time(),
    }


def _purgar_viejas():
    limite = time.time() - TTL_SEGUNDOS
    for sid in [s for s, datos in SESSIONS.items() if datos["ultimo_acceso"] < limite]:
        SESSIONS.pop(sid, None)


def obtener_sesion(cookie_id):
    _purgar_viejas()
    if cookie_id and cookie_id in SESSIONS:
        SESSIONS[cookie_id]["ultimo_acceso"] = time.time()
        return cookie_id, SESSIONS[cookie_id]
    nuevo_id = secrets.token_urlsafe(24)
    SESSIONS[nuevo_id] = _nueva_sesion()
    return nuevo_id, SESSIONS[nuevo_id]
