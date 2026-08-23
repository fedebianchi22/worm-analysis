"""
App de medición de gusanos - laboratorio de biotecnología
Subí una o más selecciones de fotos (cada una con su nombre), medí los
gusanos automáticamente (área y longitud en µm), y armá grupos de
selecciones para promediar entre sí. Todo se exporta a un único Excel.
"""
import streamlit as st
import pandas as pd
import cv2
import os
import tempfile

from measure_worms import measure_worms
from reporte_excel import generar_excel

st.set_page_config(page_title="Medición de gusanos", page_icon="🔬", layout="wide")

EXTENSIONES_VALIDAS = ["png", "jpg", "jpeg", "bmp", "tif", "tiff"]

if "seleccion_ids" not in st.session_state:
    st.session_state.seleccion_ids = [0]
    st.session_state.siguiente_seleccion_id = 1
if "grupo_ids" not in st.session_state:
    st.session_state.grupo_ids = []
    st.session_state.siguiente_grupo_id = 0
if "resultado" not in st.session_state:
    st.session_state.resultado = None

st.title("🔬 Medición automática de gusanos")
st.caption("Detecta cada gusano en las fotos, mide área y longitud en µm, y exporta todo a Excel.")

st.subheader("1. Selecciones de fotos")
st.caption("Cada selección es un grupo de fotos con su propio nombre (por ejemplo, una placa o una condición). Podés agregar varias.")

for sid in list(st.session_state.seleccion_ids):
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.text_input("Nombre de la selección", value=f"Selección {sid + 1}", key=f"nombre_{sid}")
        with col2:
            st.write("")
            if len(st.session_state.seleccion_ids) > 1:
                if st.button("🗑 Eliminar", key=f"quitar_sel_{sid}"):
                    st.session_state.seleccion_ids.remove(sid)
                    st.rerun()
        st.file_uploader(
            "Fotos de esta selección",
            type=EXTENSIONES_VALIDAS,
            accept_multiple_files=True,
            key=f"archivos_{sid}",
        )

if st.button("➕ Agregar otra selección"):
    st.session_state.seleccion_ids.append(st.session_state.siguiente_seleccion_id)
    st.session_state.siguiente_seleccion_id += 1
    st.rerun()

st.subheader("2. Grupos a promediar (opcional)")
st.caption("Si dos o más selecciones se tienen que promediar entre sí (ej: réplicas de la misma condición), armá un grupo acá. El promedio del grupo es el promedio de los promedios de cada selección incluida.")

nombres_actuales = {sid: st.session_state.get(f"nombre_{sid}", f"Selección {sid + 1}") for sid in st.session_state.seleccion_ids}

for gid in list(st.session_state.grupo_ids):
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.text_input("Nombre del grupo", value=f"Grupo {gid + 1}", key=f"nombre_grupo_{gid}")
        with col2:
            st.write("")
            if st.button("🗑 Eliminar", key=f"quitar_grupo_{gid}"):
                st.session_state.grupo_ids.remove(gid)
                st.rerun()
        st.multiselect(
            "Selecciones que integran este grupo",
            options=list(nombres_actuales.keys()),
            format_func=lambda sid: nombres_actuales.get(sid, f"Selección {sid + 1}"),
            key=f"grupo_selecciones_{gid}",
        )

if st.button("➕ Agregar grupo a promediar"):
    st.session_state.grupo_ids.append(st.session_state.siguiente_grupo_id)
    st.session_state.siguiente_grupo_id += 1
    st.rerun()

hay_fotos = any(st.session_state.get(f"archivos_{sid}") for sid in st.session_state.seleccion_ids)
procesar = st.button("▶️ Procesar todo", type="primary", disabled=not hay_fotos)

if procesar:
    carpeta_entrada_raiz = tempfile.mkdtemp(prefix="gusanos_entrada_")
    carpeta_salida_raiz = tempfile.mkdtemp(prefix="gusanos_resultados_")

    selecciones_resultado = {}
    errores_totales = []
    total_fotos = 0

    with st.spinner("Procesando fotos..."):
        for sid in st.session_state.seleccion_ids:
            nombre_sel = st.session_state.get(f"nombre_{sid}", f"Selección {sid + 1}")
            archivos = st.session_state.get(f"archivos_{sid}") or []
            if not archivos:
                continue

            carpeta_entrada = os.path.join(carpeta_entrada_raiz, str(sid))
            carpeta_salida = os.path.join(carpeta_salida_raiz, str(sid))
            os.makedirs(carpeta_entrada, exist_ok=True)
            os.makedirs(carpeta_salida, exist_ok=True)

            filas = []
            for archivo_subido in archivos:
                nombre_archivo = archivo_subido.name
                ruta_entrada = os.path.join(carpeta_entrada, nombre_archivo)
                with open(ruta_entrada, "wb") as f:
                    f.write(archivo_subido.getbuffer())

                salida_img = os.path.join(carpeta_salida, f"anotada_{nombre_archivo}")
                try:
                    res = measure_worms(ruta_entrada, salida_img)
                    if not res:
                        filas.append({"archivo": nombre_archivo, "id": None, "area_um2": None,
                                       "length_um": None, "revisar_manualmente": True,
                                       "motivo": "no se detectó ningún gusano"})
                    for r in res:
                        filas.append({"archivo": nombre_archivo, **r})
                except Exception as e:
                    errores_totales.append(f"[{nombre_sel}] {nombre_archivo}: {e}")
                total_fotos += 1

            confiables = [f for f in filas if not f["revisar_manualmente"] and f["area_um2"] is not None]
            n = len(confiables)
            promedio_area = sum(f["area_um2"] for f in confiables) / n if n else None
            promedio_length = sum(f["length_um"] for f in confiables) / n if n else None

            selecciones_resultado[sid] = {
                "nombre": nombre_sel,
                "filas": filas,
                "promedio_area": promedio_area,
                "promedio_length": promedio_length,
                "n": n,
                "carpeta_salida": carpeta_salida,
            }

        grupos_resultado = []
        for gid in st.session_state.grupo_ids:
            nombre_grupo = st.session_state.get(f"nombre_grupo_{gid}", f"Grupo {gid + 1}")
            sids_incluidos = st.session_state.get(f"grupo_selecciones_{gid}", [])
            detalle = []
            for sid in sids_incluidos:
                sel = selecciones_resultado.get(sid)
                if sel is not None:
                    detalle.append((sel["nombre"], sel["promedio_area"], sel["promedio_length"]))

            areas_validas = [a for _, a, _ in detalle if a is not None]
            lens_validas = [l for _, _, l in detalle if l is not None]
            promedio_area_grupo = sum(areas_validas) / len(areas_validas) if areas_validas else None
            promedio_length_grupo = sum(lens_validas) / len(lens_validas) if lens_validas else None

            grupos_resultado.append({
                "nombre": nombre_grupo,
                "detalle": detalle,
                "promedio_area": promedio_area_grupo,
                "promedio_length": promedio_length_grupo,
            })

        excel_path = os.path.join(carpeta_salida_raiz, "mediciones_gusanos.xlsx")
        generar_excel(list(selecciones_resultado.values()), grupos_resultado, excel_path)

    st.session_state.resultado = {
        "selecciones": selecciones_resultado,
        "grupos": grupos_resultado,
        "excel_path": excel_path,
        "total_fotos": total_fotos,
        "errores": errores_totales,
    }

resultado = st.session_state.resultado
if resultado is not None:
    st.success(f"Listo — {resultado['total_fotos']} fotos procesadas en {len(resultado['selecciones'])} selección(es).")

    if resultado["errores"]:
        with st.expander(f"⚠️ {len(resultado['errores'])} fotos con error al procesar"):
            for e in resultado["errores"]:
                st.write("-", e)

    with open(resultado["excel_path"], "rb") as f:
        st.download_button("⬇️ Descargar Excel", f, file_name="mediciones_gusanos.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="primary")

    if resultado["grupos"]:
        st.subheader("Promedios por grupo")
        for grupo in resultado["grupos"]:
            with st.container(border=True):
                st.markdown(f"**{grupo['nombre']}** — selecciones: {', '.join(n for n, _, _ in grupo['detalle']) or '(ninguna)'}")
                c1, c2 = st.columns(2)
                c1.metric("Área promedio (µm²)", f"{grupo['promedio_area']:.1f}" if grupo["promedio_area"] is not None else "sin datos")
                c2.metric("Longitud promedio (µm)", f"{grupo['promedio_length']:.1f}" if grupo["promedio_length"] is not None else "sin datos")

    for sel in resultado["selecciones"].values():
        st.divider()
        st.subheader(sel["nombre"])
        df = pd.DataFrame(sel["filas"])
        total = len(df)
        revisar = int(df["revisar_manualmente"].sum()) if total else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Gusanos detectados", total)
        c2.metric("A revisar a mano", revisar)
        c3.metric("Área promedio (µm²)", f"{sel['promedio_area']:.1f}" if sel["promedio_area"] is not None else "sin datos")
        c4.metric("Longitud promedio (µm)", f"{sel['promedio_length']:.1f}" if sel["promedio_length"] is not None else "sin datos")

        st.dataframe(df, use_container_width=True)

        st.caption("🟢 Verde = medido automáticamente · 🔴 Rojo = revisar a mano en Motic")
        archivos_unicos = df["archivo"].unique() if total else []
        cols = st.columns(3)
        for i, archivo in enumerate(archivos_unicos):
            ruta_anotada = os.path.join(sel["carpeta_salida"], f"anotada_{archivo}")
            if os.path.exists(ruta_anotada):
                img = cv2.imread(ruta_anotada)
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                with cols[i % 3]:
                    st.image(img_rgb, caption=archivo, use_column_width=True)
else:
    st.info("Subí las fotos en al menos una selección y apretá \"Procesar todo\" para empezar.")
