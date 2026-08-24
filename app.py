"""
App de medición de gusanos - laboratorio de biotecnología
Subí una o más selecciones de fotos (cada una con su nombre), medí los
gusanos automáticamente (área y longitud en µm), corregí a mano lo que
haga falta, y armá grupos de selecciones para promediar entre sí. Todo
se exporta a un único Excel.
"""
import streamlit as st
import pandas as pd
import cv2
import os
import io
import base64
import copy
import tempfile
import zipfile
from PIL import Image

from measure_worms import measure_worms, medir_desde_contorno, dibujar_overlay
from reporte_excel import generar_excel
from pen_editor import pen_editor

st.set_page_config(page_title="Medición de gusanos", page_icon="🔬", layout="wide")


def _imagen_a_data_uri(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


EXTENSIONES_VALIDAS = ["png", "jpg", "jpeg", "bmp", "tif", "tiff"]
COLUMNAS_TABLA = ["archivo", "id", "area_um2", "length_um", "revisar_manualmente", "motivo"]

if "seleccion_ids" not in st.session_state:
    st.session_state.seleccion_ids = [0]
    st.session_state.siguiente_seleccion_id = 1
if "grupo_ids" not in st.session_state:
    st.session_state.grupo_ids = []
    st.session_state.siguiente_grupo_id = 0
if "resultado" not in st.session_state:
    st.session_state.resultado = None


def calcular_promedio(filas):
    """Promedio de área/longitud usando solo las filas confiables (sin marcar para revisar)."""
    confiables = [f for f in filas if not f["revisar_manualmente"] and f.get("area_um2") is not None]
    n = len(confiables)
    if n == 0:
        return None, None, 0
    area = sum(f["area_um2"] for f in confiables) / n
    length = sum(f["length_um"] for f in confiables) / n
    return area, length, n


def calcular_promedio_grupo(sids_incluidos, selecciones_resultado):
    detalle = []
    for sid in sids_incluidos:
        sel = selecciones_resultado.get(sid)
        if sel is None:
            continue
        area, length, _ = calcular_promedio(sel["filas"])
        detalle.append((sel["nombre"], area, length))
    areas = [a for _, a, _ in detalle if a is not None]
    lens = [l for _, _, l in detalle if l is not None]
    area_grupo = sum(areas) / len(areas) if areas else None
    length_grupo = sum(lens) / len(lens) if lens else None
    return detalle, area_grupo, length_grupo


def zip_de_carpeta(carpeta, prefijo="anotada_"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for nombre in sorted(os.listdir(carpeta)):
            if nombre.startswith(prefijo):
                zf.write(os.path.join(carpeta, nombre), arcname=nombre)
    buffer.seek(0)
    return buffer


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

            selecciones_resultado[sid] = {
                "nombre": nombre_sel,
                "filas": filas,
                "carpeta_entrada": carpeta_entrada,
                "carpeta_salida": carpeta_salida,
            }

    st.session_state.resultado = {
        "selecciones": selecciones_resultado,
        "total_fotos": total_fotos,
        "errores": errores_totales,
    }

resultado = st.session_state.resultado
if resultado is not None:
    st.divider()
    st.success(f"Listo — {resultado['total_fotos']} fotos procesadas en {len(resultado['selecciones'])} selección(es).")

    if resultado["errores"]:
        with st.expander(f"⚠️ {len(resultado['errores'])} fotos con error al procesar"):
            for e in resultado["errores"]:
                st.write("-", e)

    grupos_actuales = []
    for gid in st.session_state.grupo_ids:
        nombre_grupo = st.session_state.get(f"nombre_grupo_{gid}", f"Grupo {gid + 1}")
        sids_incluidos = st.session_state.get(f"grupo_selecciones_{gid}", [])
        detalle, area_grupo, length_grupo = calcular_promedio_grupo(sids_incluidos, resultado["selecciones"])
        grupos_actuales.append({"nombre": nombre_grupo, "detalle": detalle,
                                 "promedio_area": area_grupo, "promedio_length": length_grupo})

    selecciones_para_excel = []
    for sel in resultado["selecciones"].values():
        area, length, n = calcular_promedio(sel["filas"])
        selecciones_para_excel.append({"nombre": sel["nombre"], "filas": sel["filas"],
                                        "promedio_area": area, "promedio_length": length, "n": n})

    excel_buffer_path = os.path.join(tempfile.gettempdir(), "mediciones_gusanos_actual.xlsx")
    generar_excel(selecciones_para_excel, grupos_actuales, excel_buffer_path)
    with open(excel_buffer_path, "rb") as f:
        st.download_button("⬇️ Descargar Excel", f, file_name="mediciones_gusanos.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="primary")

    if grupos_actuales:
        st.subheader("Promedios por grupo")
        for grupo in grupos_actuales:
            with st.container(border=True):
                st.markdown(f"**{grupo['nombre']}** — selecciones: {', '.join(n for n, _, _ in grupo['detalle']) or '(ninguna)'}")
                c1, c2 = st.columns(2)
                c1.metric("Área promedio (µm²)", f"{grupo['promedio_area']:.1f}" if grupo["promedio_area"] is not None else "sin datos")
                c2.metric("Longitud promedio (µm)", f"{grupo['promedio_length']:.1f}" if grupo["promedio_length"] is not None else "sin datos")

    for sid, sel in resultado["selecciones"].items():
        st.divider()
        st.subheader(sel["nombre"])

        df_visible = pd.DataFrame(sel["filas"])[COLUMNAS_TABLA] if sel["filas"] else pd.DataFrame(columns=COLUMNAS_TABLA)
        st.caption("Podés editar área, longitud y destildar \"revisar_manualmente\" una vez que lo chequeaste a mano.")
        editado = st.data_editor(
            df_visible,
            key=f"editor_{sid}",
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            disabled=["archivo", "id"],
        )
        # Sincronizar por (archivo, id) y no por posición: la tabla se puede
        # ordenar haciendo click en un header, y ahí el orden de "editado" ya
        # no coincide con el de sel["filas"] — sincronizar por índice mezclaría
        # los valores editados entre gusanos distintos.
        filas_por_clave = {(f["archivo"], f["id"]): f for f in sel["filas"]}
        for _, fila_editada in editado.iterrows():
            id_editado = fila_editada["id"]
            if pd.isna(id_editado):
                id_editado = None
            fila = filas_por_clave.get((fila_editada["archivo"], id_editado))
            if fila is None:
                continue
            fila["area_um2"] = fila_editada["area_um2"]
            fila["length_um"] = fila_editada["length_um"]
            fila["revisar_manualmente"] = bool(fila_editada["revisar_manualmente"])
            fila["motivo"] = fila_editada["motivo"]

        area, length, n = calcular_promedio(sel["filas"])
        total = len(sel["filas"])
        revisar = sum(1 for f in sel["filas"] if f["revisar_manualmente"])

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Gusanos detectados", total)
        c2.metric("A revisar a mano", revisar)
        c3.metric("Área promedio (µm²)", f"{area:.1f}" if area is not None else "sin datos")
        c4.metric("Longitud promedio (µm)", f"{length:.1f}" if length is not None else "sin datos")

        st.caption("🟢 Verde = medido automáticamente · 🔴 Rojo = revisar a mano en Motic")
        archivos_unicos = [f["archivo"] for f in sel["filas"]]
        archivos_unicos = list(dict.fromkeys(archivos_unicos))
        cols = st.columns(3)
        for i, archivo in enumerate(archivos_unicos):
            ruta_anotada = os.path.join(sel["carpeta_salida"], f"anotada_{archivo}")
            if os.path.exists(ruta_anotada):
                img = cv2.imread(ruta_anotada)
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                with cols[i % 3]:
                    st.image(img_rgb, caption=archivo, use_column_width=True)

        zip_buffer = zip_de_carpeta(sel["carpeta_salida"])
        st.download_button(
            f"⬇️ Descargar todas las fotos analizadas de \"{sel['nombre']}\" (ZIP)",
            zip_buffer,
            file_name=f"fotos_analizadas_{sel['nombre']}.zip",
            mime="application/zip",
            key=f"zip_{sid}",
        )

    st.divider()
    st.subheader("3. Corregir una detección")
    st.caption("Elegí un gusano y arrastrá los puntos de su contorno para corregirlo. Al aplicar, se recalculan área y longitud, y se destilda \"revisar_manualmente\".")

    sids_con_datos = [sid for sid, sel in resultado["selecciones"].items() if any(f.get("contorno") for f in sel["filas"])]
    if not sids_con_datos:
        st.info("Todavía no hay gusanos detectados para corregir.")
    else:
        sid_corr = st.selectbox("Selección", sids_con_datos, format_func=lambda sid: resultado["selecciones"][sid]["nombre"], key="corr_sid")
        sel_corr = resultado["selecciones"][sid_corr]
        archivos_con_datos = list(dict.fromkeys(f["archivo"] for f in sel_corr["filas"] if f.get("contorno")))
        archivo_corr = st.selectbox("Foto", archivos_con_datos, key="corr_archivo")
        if "_pendiente_corr_idx" in st.session_state:
            st.session_state["corr_idx"] = st.session_state.pop("_pendiente_corr_idx")
        filas_de_foto = [(i, f) for i, f in enumerate(sel_corr["filas"]) if f["archivo"] == archivo_corr and f.get("contorno")]
        idx_corr = st.selectbox(
            "Gusano",
            [i for i, _ in filas_de_foto],
            format_func=lambda i: f"#{sel_corr['filas'][i]['id']} (L={sel_corr['filas'][i]['length_um']}um, área={sel_corr['filas'][i]['area_um2']}um²)",
            key="corr_idx",
        )

        fila_corr = sel_corr["filas"][idx_corr]
        ruta_original = os.path.join(sel_corr["carpeta_entrada"], archivo_corr)
        img_original = cv2.imread(ruta_original)
        img_h, img_w = img_original.shape[:2]

        st.caption("¿Esta detección son en realidad 2 gusanos pegados/cruzados? Separala en 2 y después ajustá cada contorno por separado.")
        if st.button("✂️ Separar en 2 gusanos", key=f"separar_{sid_corr}_{archivo_corr}_{idx_corr}"):
            ids_existentes = [f["id"] for f in sel_corr["filas"] if f.get("id") is not None]
            siguiente_id = (max(ids_existentes) + 1) if ids_existentes else 0

            fila_a = copy.deepcopy(fila_corr)
            fila_a["id"] = siguiente_id
            fila_a["motivo"] = "dividido de una detección conjunta - falta ajustar el contorno"
            fila_a["revisar_manualmente"] = True

            fila_b = copy.deepcopy(fila_corr)
            fila_b["id"] = siguiente_id + 1
            fila_b["motivo"] = "dividido de una detección conjunta - falta ajustar el contorno"
            fila_b["revisar_manualmente"] = True

            sel_corr["filas"][idx_corr:idx_corr + 1] = [fila_a, fila_b]

            gusanos_de_la_foto = [f for f in sel_corr["filas"] if f["archivo"] == archivo_corr and f.get("contorno")]
            ruta_salida = os.path.join(sel_corr["carpeta_salida"], f"anotada_{archivo_corr}")
            dibujar_overlay(ruta_original, ruta_salida, gusanos_de_la_foto)

            st.session_state["_pendiente_corr_idx"] = idx_corr
            st.success("Separado en 2 — ahora ajustá el contorno de cada uno (arrancan superpuestos, con la misma forma).")
            st.rerun()

        version_key = f"pen_version_{sid_corr}_{archivo_corr}_{idx_corr}"
        if version_key not in st.session_state:
            st.session_state[version_key] = 0

        # "contorno_control" son los puntos que el usuario edita a mano (pocos,
        # manejables, con manijas de curvatura por punto); "contorno" es el
        # trazado ya aplanado en muchos puntos finos, usado para dibujar y medir.
        contorno_control_guardado = fila_corr.get("contorno_control")
        if contorno_control_guardado:
            contorno_inicial = contorno_control_guardado
        else:
            contorno_inicial = [{"x": px, "y": py, "curved": False, "hx": 0, "hy": 0} for px, py in fila_corr["contorno"]]

        xs = [p["x"] for p in contorno_inicial]
        ys = [p["y"] for p in contorno_inicial]
        margen = 40
        x0 = int(max(0, min(xs) - margen))
        y0 = int(max(0, min(ys) - margen))
        x1 = int(min(img_w, max(xs) + margen))
        y1 = int(min(img_h, max(ys) + margen))

        crop = cv2.cvtColor(img_original[y0:y1, x0:x1], cv2.COLOR_BGR2RGB)
        crop_h, crop_w = crop.shape[:2]

        objetivo = 560
        escala = min(3.5, max(1.0, objetivo / max(crop_w, crop_h)))
        canvas_w, canvas_h = int(crop_w * escala), int(crop_h * escala)

        crop_img = Image.fromarray(crop).resize((canvas_w, canvas_h))
        puntos_canvas = [
            {
                "x": (p["x"] - x0) * escala, "y": (p["y"] - y0) * escala,
                "curved": p["curved"], "hx": p["hx"] * escala, "hy": p["hy"] * escala,
            }
            for p in contorno_inicial
        ]

        st.caption(
            "Click en la línea amarilla para agregar un punto ahí. Arrastrá un punto verde para moverlo "
            "(la línea se actualiza en vivo). Click en un punto sin arrastrar abre un menú para eliminarlo "
            "o convertirlo en punto curvo (con sus propias manijas, como en Illustrator) — así podés dejar "
            "tramos rectos y curvar solo donde haga falta."
        )
        pen_key = f"pen_{sid_corr}_{archivo_corr}_{idx_corr}_v{st.session_state[version_key]}"
        resultado_pen = pen_editor(_imagen_a_data_uri(crop_img), canvas_w, canvas_h, puntos_canvas, key=pen_key)

        col_a, col_b = st.columns(2)
        with col_a:
            reiniciar = st.button("🔄 Reiniciar al último aplicado", key=f"reiniciar_{pen_key}")
        with col_b:
            aplicar = st.button("✅ Aplicar corrección", key=f"aplicar_{pen_key}", type="primary")

        if reiniciar:
            st.session_state[version_key] += 1
            st.rerun()

        if aplicar:
            puntos_editados = resultado_pen.get("points") or []
            if len(puntos_editados) < 3:
                st.error("Hacen falta al menos 3 puntos.")
            else:
                nuevo_control = [
                    {
                        "x": x0 + p["x"] / escala, "y": y0 + p["y"] / escala,
                        "curved": p["curved"], "hx": p["hx"] / escala, "hy": p["hy"] / escala,
                    }
                    for p in puntos_editados
                ]
                medicion = medir_desde_contorno(nuevo_control, img_original.shape)
                fila_corr["area_um2"] = medicion["area_um2"]
                fila_corr["length_um"] = medicion["length_um"]
                fila_corr["contorno"] = medicion["contorno_dibujo"]
                fila_corr["contorno_control"] = nuevo_control
                fila_corr["skel_points"] = medicion["skel_points"]
                fila_corr["posible_cruce"] = medicion["posible_cruce"]
                fila_corr["revisar_manualmente"] = False
                fila_corr["motivo"] = "corregido manualmente"

                gusanos_de_la_foto = [f for f in sel_corr["filas"] if f["archivo"] == archivo_corr and f.get("contorno")]
                ruta_salida = os.path.join(sel_corr["carpeta_salida"], f"anotada_{archivo_corr}")
                dibujar_overlay(ruta_original, ruta_salida, gusanos_de_la_foto)

                st.session_state[version_key] += 1
                st.success("Corrección aplicada.")
                st.rerun()
else:
    st.info("Subí las fotos en al menos una selección y apretá \"Procesar todo\" para empezar.")
