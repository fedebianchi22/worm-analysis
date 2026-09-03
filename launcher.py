"""
Punto de entrada del ejecutable: levanta la app de Streamlit
en localhost y abre el navegador automáticamente.
"""
import os
import sys
import threading
import webbrowser
import time
from streamlit.web import cli as stcli
from updater import verificar_actualizacion


def abrir_navegador():
    time.sleep(2.5)
    webbrowser.open("http://localhost:8501")


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    app_path = os.path.join(base_path, "app.py")

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

    # Evita que Streamlit se quede esperando el mail de bienvenida
    # (bloquea la terminal en el primer uso si no se hace esto)
    streamlit_config_dir = os.path.join(os.path.expanduser("~"), ".streamlit")
    os.makedirs(streamlit_config_dir, exist_ok=True)
    credentials_path = os.path.join(streamlit_config_dir, "credentials.toml")
    if not os.path.exists(credentials_path):
        with open(credentials_path, "w") as f:
            f.write('[general]\nemail = ""\n')

    # El exe empaquetado corre con el directorio de trabajo del .exe, no el de
    # _internal donde queda copiado .streamlit/config.toml — así que el tema
    # (paleta violeta) no se aplicaría solo con ese archivo. Lo escribimos
    # también en la config global del usuario, que Streamlit siempre lee.
    config_path = os.path.join(streamlit_config_dir, "config.toml")
    if not os.path.exists(config_path):
        with open(config_path, "w") as f:
            f.write(
                '[theme]\n'
                'base = "light"\n'
                'primaryColor = "#7C4FE0"\n'
                'backgroundColor = "#FBF9FD"\n'
                'secondaryBackgroundColor = "#EEE6F9"\n'
                'textColor = "#2B1B44"\n'
                'font = "sans serif"\n'
            )

    threading.Thread(target=abrir_navegador, daemon=True).start()

    sys.argv = [
        "streamlit", "run", app_path,
        "--global.developmentMode=false",
        "--server.headless=true",
        "--server.port=8501",
        "--browser.gatherUsageStats=false",
    ]
    sys.exit(stcli.main())
