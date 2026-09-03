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
import zipfile

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
    Devuelve (version_nueva, url_zip) si en GitHub hay una versión más
    nueva que la instalada, o None si no hay internet, no hay releases
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

    url_zip = None
    for asset in datos.get("assets", []):
        if asset.get("name", "").lower().endswith(".zip"):
            url_zip = asset.get("browser_download_url")
            break

    if not url_zip:
        return None

    return version_remota, url_zip


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


def descargar_y_aplicar(url_zip, install_dir, exe_path):
    """
    Descarga el .zip de la nueva versión y programa el reemplazo de los
    archivos actuales para cuando este proceso se cierre (Windows no deja
    sobrescribir un .exe mientras está corriendo). Termina cerrando el
    programa actual para que el reemplazo se complete.
    """
    tmp_dir = tempfile.mkdtemp(prefix="celab_update_")
    zip_path = os.path.join(tmp_dir, "actualizacion.zip")
    extract_dir = os.path.join(tmp_dir, "extraido")

    urllib.request.urlretrieve(url_zip, zip_path)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)

    # El .zip publicado trae la carpeta CElegansLab/ adentro en vez del
    # contenido suelto: si hay una única subcarpeta, usamos esa como raíz.
    contenido = os.listdir(extract_dir)
    if len(contenido) == 1 and os.path.isdir(os.path.join(extract_dir, contenido[0])):
        extract_dir = os.path.join(extract_dir, contenido[0])

    bat_path = os.path.join(tmp_dir, "actualizar.bat")
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(
            "@echo off\n"
            "timeout /t 2 /nobreak > NUL\n"
            f'robocopy "{extract_dir}" "{install_dir}" /E /IS /IT\n'
            f'start "" "{exe_path}"\n'
            f'rmdir /s /q "{tmp_dir}"\n'
        )

    subprocess.Popen(["cmd", "/c", bat_path], creationflags=subprocess.CREATE_NEW_CONSOLE)
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
        version_nueva, url_zip = resultado
        if mostrar_modal_actualizacion(version_nueva):
            install_dir = os.path.dirname(sys.executable)
            print(f"Descargando la actualización {version_nueva}...")
            descargar_y_aplicar(url_zip, install_dir, sys.executable)
    except Exception as e:
        print(f"No se pudo comprobar si hay actualizaciones: {e}")
