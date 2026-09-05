"""
Punto de entrada del programa: levanta el servidor de C. elegans Lab en
localhost, abre el navegador, y queda como un ícono en la bandeja del
sistema (sin ventana de consola — nada que pueda asustar a alguien que no
sabe de programación). Desde el ícono se puede reabrir el navegador o
cerrar el programa.
"""
import io
import os
import sys
import threading
import webbrowser
import time

from updater import verificar_actualizacion

URL_APP = "http://localhost:8501"


def _preparar_logs():
    """Sin consola (build de ventana), sys.stdout/stderr son None: hay que
    redirigirlos a un archivo para que un print() no rompa nada, y para
    poder diagnosticar un problema sin mostrarle una ventana negra a nadie."""
    carpeta = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "CElegansLab", "logs")
    os.makedirs(carpeta, exist_ok=True)
    log = open(os.path.join(carpeta, "app.log"), "a", encoding="utf-8", buffering=1)
    sys.stdout = log
    sys.stderr = log


def _icono_bandeja():
    """Ícono simple (un círculo violeta) generado en el momento, para no
    tener que empaquetar un archivo de imagen aparte."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, 60, 60), fill=(124, 79, 224, 255))
    return img


def _iniciar_bandeja():
    import pystray

    def abrir(icon, item):
        webbrowser.open(URL_APP)

    def salir(icon, item):
        icon.stop()
        os._exit(0)

    icon = pystray.Icon(
        "CElegansLab",
        icon=_icono_bandeja(),
        title="C. elegans Lab",
        menu=pystray.Menu(
            pystray.MenuItem("Abrir C. elegans Lab", abrir, default=True),
            pystray.MenuItem("Salir", salir),
        ),
    )
    icon.run()  # bloquea: debe correr en el hilo principal


def _abrir_navegador_una_vez():
    time.sleep(1.5)
    webbrowser.open(URL_APP)


def _iniciar_servidor():
    import uvicorn
    from server import app
    uvicorn.run(app, host="127.0.0.1", port=8501, log_level="warning")


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
        if sys.stdout is None:
            _preparar_logs()
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    print("Iniciando C. elegans Lab...")

    verificar_actualizacion(base_path)

    threading.Thread(target=_iniciar_servidor, daemon=True).start()
    threading.Thread(target=_abrir_navegador_una_vez, daemon=True).start()

    if getattr(sys, "frozen", False):
        _iniciar_bandeja()
    else:
        # En desarrollo (no empaquetado) es más cómodo dejar la consola
        # normal corriendo y cortar con Ctrl+C, sin ícono de bandeja.
        threading.Event().wait()
