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


def descargar_y_aplicar(url_zip, install_dir):
    """
    Descarga el .zip con el instalador de la nueva versión (mostrando una
    ventana con barra de progreso — antes esto pasaba en silencio total y
    parecía que no hacía nada), lo extrae, y corre el instalador en modo
    /SILENT (con barra de progreso propia, sin pasos para clickear)
    apuntando a la misma carpeta donde ya está instalado. El instalador
    (Inno Setup, CloseApplications=force) cierra este programa solo antes
    de copiar los archivos nuevos y lo vuelve a abrir al terminar.
    """
    import threading
    import tkinter as tk
    from tkinter import ttk

    estado = {"pct": 0, "instalador_path": None, "error": None}

    def _reporthook(bloque, tam_bloque, tam_total):
        if tam_total > 0:
            estado["pct"] = min(100, bloque * tam_bloque * 100 / tam_total)

    def _trabajo():
        try:
            tmp_dir = tempfile.mkdtemp(prefix="celab_update_")
            zip_path = os.path.join(tmp_dir, "actualizacion.zip")
            urllib.request.urlretrieve(url_zip, zip_path, reporthook=_reporthook)

            extract_dir = os.path.join(tmp_dir, "extraido")
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(extract_dir)

            for nombre in os.listdir(extract_dir):
                if nombre.lower().endswith(".exe"):
                    estado["instalador_path"] = os.path.join(extract_dir, nombre)
                    break
        except Exception as e:
            estado["error"] = str(e)

    hilo = threading.Thread(target=_trabajo, daemon=True)
    hilo.start()

    ventana = tk.Tk()
    ventana.title("C. elegans Lab")
    ventana.resizable(False, False)
    ventana.attributes("-topmost", True)
    ventana.eval("tk::PlaceWindow . center")
    tk.Label(ventana, text="Descargando la actualización...\nNo cierres esta ventana.",
             padx=28, pady=16, justify="center").pack()
    barra = ttk.Progressbar(ventana, mode="determinate", maximum=100, length=280)
    barra.pack(padx=28, pady=(0, 20))

    def _revisar():
        barra["value"] = estado["pct"]
        if hilo.is_alive():
            ventana.after(150, _revisar)
        else:
            ventana.destroy()

    ventana.after(150, _revisar)
    ventana.mainloop()

    if estado["error"] or not estado["instalador_path"]:
        return  # falló la descarga: no bloquea el arranque normal del programa

    subprocess.Popen(
        [estado["instalador_path"], "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DIR=" + install_dir],
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
        version_nueva, url_zip = resultado
        if mostrar_modal_actualizacion(version_nueva):
            install_dir = os.path.dirname(sys.executable)
            print(f"Descargando la actualización {version_nueva}...")
            descargar_y_aplicar(url_zip, install_dir)
    except Exception as e:
        print(f"No se pudo comprobar si hay actualizaciones: {e}")
