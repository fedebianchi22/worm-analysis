"""
Actualizador automático del ejecutable: compara la versión instalada contra
la última publicada en GitHub Releases y, si hay una más nueva, ofrece
descargarla y reemplazar la instalación actual sin pasos manuales.
"""
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

REPO = "fedebianchi22/worm-analysis"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
TIMEOUT_SEG = 4


def _version_local(base_path):
    version_path = os.path.join(base_path, "VERSION")
    try:
        with open(version_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "0.0.0"


def _a_tupla(version):
    version = version.strip().lstrip("vV")
    partes = []
    for parte in version.split("."):
        try:
            partes.append(int(parte))
        except ValueError:
            partes.append(0)
    while len(partes) < 3:
        partes.append(0)
    return tuple(partes[:3])


def buscar_actualizacion(base_path):
    """
    Devuelve (version_nueva, url_instalador) si en GitHub hay una versión
    más nueva que la instalada, o None si no hay internet, no hay releases
    publicados, o ya está actualizado.
    """
    try:
        req = urllib.request.Request(
            API_URL, headers={"Accept": "application/vnd.github+json"}
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEG) as resp:
            datos = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    version_remota = datos.get("tag_name", "")
    if not version_remota:
        return None

    if _a_tupla(version_remota) <= _a_tupla(_version_local(base_path)):
        return None

    url_instalador = None
    for asset in datos.get("assets", []):
        nombre = asset.get("name", "").lower()
        if nombre.endswith(".exe") and "setup" in nombre:
            url_instalador = asset.get("browser_download_url")
            break

    if not url_instalador:
        return None

    return version_remota, url_instalador


def mostrar_modal_actualizacion(version_nueva):
    """Muestra un aviso simple con Sí/No. Devuelve True si el usuario acepta."""
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    respuesta = messagebox.askyesno(
        "Actualización disponible",
        f"Hay una nueva versión de C. elegans Lab disponible ({version_nueva}).\n\n"
        "¿Querés actualizar ahora?\n\n"
        "El programa se va a cerrar y volver a abrir solo. No tarda más de un minuto.",
        parent=root,
    )
    root.destroy()
    return respuesta


def descargar_y_aplicar(url_instalador, install_dir):
    """
    Descarga el instalador de la nueva versión y lo corre en modo
    silencioso, apuntando a la misma carpeta donde ya está instalado. El
    instalador (Inno Setup, CloseApplications=force) cierra este programa
    solo antes de copiar los archivos nuevos y lo vuelve a abrir al
    terminar — no aparece ninguna ventana en todo el proceso.
    """
    tmp_dir = tempfile.mkdtemp(prefix="celab_update_")
    instalador_path = os.path.join(tmp_dir, "CElegansLab-Setup.exe")
    urllib.request.urlretrieve(url_instalador, instalador_path)

    subprocess.Popen(
        [instalador_path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DIR=" + install_dir],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    os._exit(0)


def verificar_actualizacion(base_path):
    """Chequea, avisa y aplica una actualización si el usuario acepta. No hace
    nada (ni tira error) si algo falla: nunca debe bloquear el arranque normal."""
    if not getattr(sys, "frozen", False):
        return
    try:
        resultado = buscar_actualizacion(base_path)
        if resultado is None:
            return
        version_nueva, url_instalador = resultado
        if mostrar_modal_actualizacion(version_nueva):
            install_dir = os.path.dirname(sys.executable)
            print(f"Descargando la actualización {version_nueva}...")
            descargar_y_aplicar(url_instalador, install_dir)
    except Exception as e:
        print(f"No se pudo comprobar si hay actualizaciones: {e}")
