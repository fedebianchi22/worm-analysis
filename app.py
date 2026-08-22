"""
App de medición de gusanos - laboratorio de biotecnología
Selecciona una carpeta de fotos, mide automáticamente cada gusano
(área y longitud en µm) y exporta los resultados a Excel.
"""
import streamlit as st
import pandas as pd
import cv2
import os
import glob
import tempfile
import threading
from datetime import datetime

from measure_worms import measure_worms

st.set_page_config(page_title="Medición de gusanos", page_icon="🔬", layout="wide")

EXTENSIONES_VALIDAS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")

if "carpeta" not in st.session_state:
    st.session_state.carpeta = ""
if "resultados" not in st.session_state:
    st.session_state.resultados = None
if "carpeta_salida" not in st.session_state:
    st.session_state.carpeta_salida = None


def elegir_carpeta():
    """Abre el explorador de carpetas nativo de Windows y guarda la ruta elegida."""
    import tkinter as tk
    from tkinter import filedialog

    resultado = {"ruta": ""}

    def _abrir():
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)
        resultado["ruta"] = filedialog.askdirectory(title="Elegí la carpeta con las fotos de gusanos")
        root.destroy()

    hilo = threading.Thread(target=_abrir)
    hilo.start()
    hilo.join()
    if resultado["ruta"]:
        st.session_state.carpeta = resultado["ruta"]


st.title("🔬 Medición automática de gusanos")
st.caption("Detecta cada gusano en las fotos, mide área y longitud en µm, y exporta todo a Excel.")

col1, col2 = st.columns([3, 1])
with col1:
    st.text_input("Carpeta seleccionada", value=st.session_state.carpeta, disabled=True, label_visibility="collapsed", placeholder="Ninguna carpeta seleccionada todavía")
with col2:
    st.button("📁 Elegir carpeta", on_click=elegir_carpeta, use_container_width=True)

procesar = st.button("▶️ Procesar todas las fotos", type="primary", disabled=not st.session_state.carpeta)

if procesar:
    carpeta = st.session_state.carpeta
    archivos = []
    for ext in EXTENSIONES_VALIDAS:
        archivos.extend(glob.glob(os.path.join(carpeta, f"*{ext}")))
        archivos.extend(glob.glob(os.path.join(carpeta, f"*{ext.upper()}")))
    archivos = sorted(set(archivos))

    if not archivos:
        st.warning("No encontré fotos (png/jpg/jpeg/bmp/tif) en esa carpeta.")
    else:
        carpeta_salida = os.path.join(carpeta, f"resultados_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(carpeta_salida, exist_ok=True)

        filas = []
        progreso = st.progress(0, text="Procesando fotos...")
        errores = []

        for idx, archivo in enumerate(archivos):
            nombre = os.path.basename(archivo)
            salida_img = os.path.join(carpeta_salida, f"anotada_{nombre}")
            try:
                res = measure_worms(archivo, salida_img)
                if not res:
                    filas.append({"archivo": nombre, "id": None, "area_um2": None,
                                   "length_um": None, "revisar_manualmente": True,
                                   "motivo": "no se detectó ningún gusano"})
                for r in res:
                    filas.append({"archivo": nombre, **r})
            except Exception as e:
                errores.append(f"{nombre}: {e}")
            progreso.progress((idx + 1) / len(archivos), text=f"Procesando {nombre} ({idx+1}/{len(archivos)})")

        progreso.empty()

        df = pd.DataFrame(filas)
        excel_path = os.path.join(carpeta_salida, "mediciones_gusanos.xlsx")
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Mediciones")
            ws = writer.sheets["Mediciones"]
            for col in ws.columns:
                max_len = max(len(str(c.value)) for c in col) + 2
                ws.column_dimensions[col[0].column_letter].width = max_len

        st.session_state.resultados = df
        st.session_state.carpeta_salida = carpeta_salida
        st.session_state.archivos_procesados = len(archivos)
        st.session_state.errores = errores

if st.session_state.resultados is not None:
    df = st.session_state.resultados
    st.success(f"Listo — {st.session_state.archivos_procesados} fotos procesadas. Resultados guardados en:\n\n`{st.session_state.carpeta_salida}`")

    if st.session_state.get("errores"):
        with st.expander(f"⚠️ {len(st.session_state.errores)} fotos con error al procesar"):
            for e in st.session_state.errores:
                st.write("-", e)

    total = len(df)
    ok = len(df[df["revisar_manualmente"] == False])
    revisar = len(df[df["revisar_manualmente"] == True])

    c1, c2, c3 = st.columns(3)
    c1.metric("Gusanos detectados", total)
    c2.metric("Medidos automáticamente", ok)
    c3.metric("A revisar a mano", revisar)

    with open(os.path.join(st.session_state.carpeta_salida, "mediciones_gusanos.xlsx"), "rb") as f:
        st.download_button("⬇️ Descargar Excel", f, file_name="mediciones_gusanos.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="primary")

    st.dataframe(df, use_container_width=True)

    st.subheader("Fotos anotadas")
    st.caption("🟢 Verde = medido automáticamente · 🔴 Rojo = revisar a mano en Motic")

    archivos_unicos = df["archivo"].unique()
    cols = st.columns(3)
    for i, archivo in enumerate(archivos_unicos):
        ruta_anotada = os.path.join(st.session_state.carpeta_salida, f"anotada_{archivo}")
        if os.path.exists(ruta_anotada):
            img = cv2.imread(ruta_anotada)
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            with cols[i % 3]:
                st.image(img_rgb, caption=archivo, use_column_width=True)
else:
    st.info("Elegí una carpeta con fotos y apretá \"Procesar todas las fotos\" para empezar.")
