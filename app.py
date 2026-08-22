"""
App de medición de gusanos - laboratorio de biotecnología
Subí fotos de gusanos, los mide automáticamente (área y longitud en µm)
y exporta los resultados a Excel.
"""
import streamlit as st
import pandas as pd
import cv2
import os
import tempfile

from measure_worms import measure_worms

st.set_page_config(page_title="Medición de gusanos", page_icon="🔬", layout="wide")

EXTENSIONES_VALIDAS = ["png", "jpg", "jpeg", "bmp", "tif", "tiff"]

if "resultados" not in st.session_state:
    st.session_state.resultados = None
if "carpeta_salida" not in st.session_state:
    st.session_state.carpeta_salida = None

st.title("🔬 Medición automática de gusanos")
st.caption("Detecta cada gusano en las fotos, mide área y longitud en µm, y exporta todo a Excel.")

archivos_subidos = st.file_uploader(
    "Subí las fotos de los gusanos",
    type=EXTENSIONES_VALIDAS,
    accept_multiple_files=True,
)

procesar = st.button("▶️ Procesar todas las fotos", type="primary", disabled=not archivos_subidos)

if procesar:
    carpeta_entrada = tempfile.mkdtemp(prefix="gusanos_entrada_")
    carpeta_salida = tempfile.mkdtemp(prefix="gusanos_resultados_")

    filas = []
    progreso = st.progress(0, text="Procesando fotos...")
    errores = []

    for idx, archivo_subido in enumerate(archivos_subidos):
        nombre = archivo_subido.name
        ruta_entrada = os.path.join(carpeta_entrada, nombre)
        with open(ruta_entrada, "wb") as f:
            f.write(archivo_subido.getbuffer())

        salida_img = os.path.join(carpeta_salida, f"anotada_{nombre}")
        try:
            res = measure_worms(ruta_entrada, salida_img)
            if not res:
                filas.append({"archivo": nombre, "id": None, "area_um2": None,
                               "length_um": None, "revisar_manualmente": True,
                               "motivo": "no se detectó ningún gusano"})
            for r in res:
                filas.append({"archivo": nombre, **r})
        except Exception as e:
            errores.append(f"{nombre}: {e}")
        progreso.progress((idx + 1) / len(archivos_subidos), text=f"Procesando {nombre} ({idx+1}/{len(archivos_subidos)})")

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
    st.session_state.archivos_procesados = len(archivos_subidos)
    st.session_state.errores = errores

if st.session_state.resultados is not None:
    df = st.session_state.resultados
    st.success(f"Listo — {st.session_state.archivos_procesados} fotos procesadas.")

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
    st.info("Subí las fotos de los gusanos y apretá \"Procesar todas las fotos\" para empezar.")
