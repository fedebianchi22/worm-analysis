"""
Punto de entrada del ejecutable: levanta el servidor de C. elegans Lab
en localhost y abre el navegador automáticamente.
"""
import os
import sys
import threading
import webbrowser
import time

from updater import verificar_actualizacion


def abrir_navegador():
    time.sleep(1.5)
    webbrowser.open("http://localhost:8501")


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    print("=" * 60)
    print("  C. ELEGANS LAB")
    print("=" * 60)
    print()
    print("  Iniciando el programa, puede tardar unos segundos...")
    print("  El programa ya se abrió en tu navegador.")
    print("  Si no se abrió solo, entrá a: http://localhost:8501")
    print()
    print("  >>> NO CIERRES ESTA VENTANA mientras estés usando el programa <<<")
    print("  >>> Para salir del programa, cerrá esta ventana negra <<<")
    print()
    print("=" * 60)

    verificar_actualizacion(base_path)

    threading.Thread(target=abrir_navegador, daemon=True).start()

    import uvicorn
    from server import app

    uvicorn.run(app, host="127.0.0.1", port=8501, log_level="warning")
