"""
C. elegans Lab — medición automática de nematodos en fotos de microscopio.
Subí una o más selecciones de fotos (cada una con su nombre y objetivo), medí
los gusanos automáticamente (área y longitud en µm), corregí a mano lo que
haga falta, y armá grupos de selecciones para promediar entre sí. Todo se
exporta a un único Excel.
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

from measure_worms import measure_worms, medir_desde_contorno, dibujar_overlay, OBJETIVOS_CALIBRADOS, OBJETIVO_POR_DEFECTO
from reporte_excel import generar_excel
from pen_editor import pen_editor

st.set_page_config(page_title="C. elegans Lab", page_icon="🪱", layout="wide")

CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

  :root {
    --accent: #7C4FE0;
    --accent-strong: #6636C8;
    --accent-soft: #EEE6F9;
    --surface-2: #F3EEFA;
    --border: #E1D6F2;
    --border-strong: #CBB9E8;
    --text: #2B1B44;
    --text-muted: #6E5D8C;
    --text-faint: #9C8CB8;
    --ok: #1F8A5F;
    --ok-soft: #E4F5EC;
    --ok-border: #BCE3CE;
    --warn: #9A5B00;
    --warn-soft: #FBEEDA;
    --warn-border: #EFD3A0;
  }

  /* La app tiene un único tema (violeta, definido en .streamlit/config.toml)
     con buen contraste. El menú de Streamlit dejaba pasar a un tema "Dark"
     genérico que no lo respetaba, así que se oculta (client.toolbarMode =
     "minimal") junto con la franja de color decorativa de arriba. */
  [data-testid="stDecoration"] { display: none; }

  html, body, .stApp, [class*="css"] { font-family: 'IBM Plex Sans', -apple-system, sans-serif; }
  h1, h2, h3, h1.screen-title { font-family: 'IBM Plex Serif', Georgia, serif; color: var(--text); }
  [data-testid="stMetricValue"], .num, .tile-value { font-family: 'IBM Plex Mono', 'SFMono-Regular', monospace; }
  div[data-testid="stExpander"] details summary p { color: var(--accent-strong); }

  .stButton > button, .stDownloadButton > button { border-radius: 9px; font-weight: 600; }
  .stButton > button[kind="primary"] { background-color: var(--accent); border-color: var(--accent); }
  .stButton > button[kind="primary"]:hover { background-color: var(--accent-strong); border-color: var(--accent-strong); }
  .stDownloadButton > button[kind="primary"] { background-color: var(--accent); border-color: var(--accent); }
  .stDownloadButton > button[kind="primary"]:hover { background-color: var(--accent-strong); border-color: var(--accent-strong); }
  .stLinkButton > a[kind="primary"]:hover { background-color: var(--accent-strong); border-color: var(--accent-strong); }

  [data-testid="stSidebar"] { background: var(--surface-2); border-right: 1px solid var(--border); }
  [data-testid="stSidebar"] .stButton > button { text-align: left; justify-content: flex-start; width: 100%; }

  .brand-block { padding: 2px 2px 16px; }
  .brand-row { display: flex; align-items: center; gap: 10px; }
  .brand-icon {
    width: 32px; height: 32px; border-radius: 8px; background: var(--accent); color: #fff;
    display: flex; align-items: center; justify-content: center; font-size: 16px; flex: none;
  }
  .brand-name { font-family: 'IBM Plex Serif', serif; font-weight: 600; font-size: 1.05rem; line-height: 1.2; color: var(--text); }
  .brand-tag { margin-top: 8px; font-size: .68rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: .07em; }

  .eyebrow { font-family: 'IBM Plex Mono', monospace; font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; color: var(--accent); margin-bottom: 2px; }
  h1.screen-title { font-weight: 600; font-size: 1.7rem; margin: 4px 0 6px !important; letter-spacing: -.01em; }
  p.screen-sub { color: var(--text-muted); font-size: .92rem; max-width: 68ch; line-height: 1.55; margin-bottom: 1.1rem; }

  .tile { background: #fff; border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px 12px; height: 100%; }
  .tile-label { font-size: .7rem; color: var(--text-muted); font-weight: 600; }
  .tile-value { font-size: 1.55rem; font-weight: 600; margin-top: 5px; letter-spacing: -.02em; color: var(--text); }
  .tile-unit { font-size: .88rem; color: var(--text-muted); font-weight: 500; font-family: 'IBM Plex Sans', sans-serif; }
  .tile-sub { font-size: .7rem; color: var(--text-faint); margin-top: 3px; font-family: 'IBM Plex Sans', sans-serif; }
  .tile.ok .tile-value { color: var(--ok); }
  .tile.warn .tile-value { color: var(--warn); }

  .context-bar {
    padding: 10px 14px; background: var(--surface-2); border: 1px solid var(--border);
    border-radius: 10px; font-size: .84rem; color: var(--text-muted); margin-bottom: 14px;
  }
  .context-bar strong { color: var(--text); }

  .scale-legend { display: flex; gap: 18px; font-size: .74rem; color: var(--text-muted); margin: 4px 0 2px; }
  .scale-legend span { display: inline-flex; align-items: center; gap: 6px; }
  .scale-legend .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }

  .steps-list { list-style: none; padding: 0; margin: 4px 0 14px; }
  .steps-list li { display: flex; gap: 10px; font-size: .86rem; line-height: 1.5; margin-bottom: 8px; color: var(--text); }
  .steps-list .n {
    flex: none; width: 20px; height: 20px; border-radius: 50%; background: var(--accent-soft); color: var(--accent-strong);
    font-family: 'IBM Plex Mono', monospace; font-size: .68rem; display: flex; align-items: center; justify-content: center; margin-top: 1px;
  }

  .export-file {
    font-family: 'IBM Plex Mono', monospace; font-size: .74rem; color: var(--text-faint);
    background: var(--surface-2); padding: 5px 9px; border-radius: 6px; display: inline-block; margin-bottom: 4px;
  }

  /* Traducción del selector de archivos (Streamlit no permite cambiar estos
     textos por parámetro; se reemplaza el contenido visual y se oculta el
     texto original en inglés). */
  [data-testid="stFileUploaderDropzoneInstructions"] div > span { font-size: 0; }
  [data-testid="stFileUploaderDropzoneInstructions"] div > span::after {
    font-size: 1rem;
    content: "Arrastrá tus fotos acá";
  }
  [data-testid="stFileUploaderDropzoneInstructions"] div > small { font-size: 0; }
  [data-testid="stFileUploaderDropzoneInstructions"] div > small::after {
    font-size: 0.8rem;
    content: "Hasta 200 MB por foto · PNG, JPG, JPEG, BMP, TIF, TIFF";
  }
  [data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-secondary"] { font-size: 0; }
  [data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-secondary"]::after {
    font-size: 0.875rem;
    content: "Elegir archivos";
  }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def _imagen_a_data_uri(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _num_ar(valor, decimales=0):
    """Formatea un número con el separador de miles usual en Argentina (punto)."""
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "@").replace(".", ",").replace("@", ".")


def _screen_header(eyebrow, titulo, sub):
    st.markdown(f'<div class="eyebrow">{eyebrow}</div>', unsafe_allow_html=True)
    st.markdown(f'<h1 class="screen-title">{titulo}</h1>', unsafe_allow_html=True)
    st.markdown(f'<p class="screen-sub">{sub}</p>', unsafe_allow_html=True)


def _tile_html(label, valor, unidad, sub, variante=""):
    clase = f"tile {variante}".strip()
    return (
        f'<div class="{clase}"><div class="tile-label">{label}</div>'
        f'<div class="tile-value">{valor} <span class="tile-unit">{unidad}</span></div>'
        f'<div class="tile-sub">{sub}</div></div>'
    )


def _svg_escala_referencia(filas):
    """Ubica la longitud de cada gusano contra los rangos de referencia por
    estadio (L1 / L2-L4 / adulto) — mismos rangos que documenta el README."""
    valores = [(f["length_um"], f["revisar_manualmente"]) for f in filas if f.get("length_um") is not None]
    if not valores:
        return ""

    max_val = max(v for v, _ in valores)
    escala_max = max(1200, round(max_val * 1.1 / 100) * 100)
    margen_izq, ancho_plot = 60, 680

    def x(valor):
        return margen_izq + (valor / escala_max) * ancho_plot

    def banda(desde, hasta, color):
        return f'<rect x="{x(desde):.1f}" y="30" width="{(x(hasta) - x(desde)):.1f}" height="46" fill="{color}"/>'

    svg_bandas = banda(200, 300, "#F3EEFA") + banda(300, 950, "#FBF9FD") + banda(1000, 1100, "#EEE6F9")
    svg_etiquetas = (
        f'<text x="{x(250):.1f}" y="24" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-size="10" fill="#9C8CB8">L1</text>'
        f'<text x="{x(625):.1f}" y="24" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-size="10" fill="#9C8CB8">L2-L4</text>'
        f'<text x="{x(1050):.1f}" y="24" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-size="10" fill="#7C4FE0">Adulto</text>'
    )

    svg_ticks = ""
    for tv in [0, 250, 500, 750, 1000, escala_max]:
        xt = x(tv)
        etiqueta = _num_ar(tv) + (" µm" if tv == escala_max else "")
        svg_ticks += (
            f'<line x1="{xt:.1f}" y1="76" x2="{xt:.1f}" y2="82" stroke="#CBB9E8"/>'
            f'<text x="{xt:.1f}" y="96" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-size="10" fill="#9C8CB8">{etiqueta}</text>'
        )

    svg_puntos = ""
    for i, (valor, revisar) in enumerate(valores):
        cx = x(valor)
        cy = 66 if i % 2 == 0 else 82
        color = "#9A5B00" if revisar else "#1F8A5F"
        svg_puntos += f'<circle cx="{cx:.1f}" cy="{cy}" r="5.5" fill="{color}" stroke="#FFFFFF" stroke-width="1.5"/>'

    return (
        '<svg viewBox="0 0 800 118" width="100%" height="118" role="img" '
        'aria-label="Longitud de cada gusano comparada con los rangos de referencia por estadio">'
        f'{svg_bandas}{svg_etiquetas}'
        f'<line x1="{margen_izq}" y1="76" x2="{margen_izq + ancho_plot}" y2="76" stroke="#CBB9E8"/>'
        f'{svg_ticks}{svg_puntos}</svg>'
    )


EXTENSIONES_VALIDAS = ["png", "jpg", "jpeg", "bmp", "tif", "tiff"]
COLUMNAS_TABLA = ["archivo", "id", "area_um2", "length_um", "revisar_manualmente", "motivo"]
OPCIONES_OBJETIVO = list(OBJETIVOS_CALIBRADOS.keys())
URL_DESCARGA_PC = "https://github.com/fedebianchi22/worm-analysis/releases/latest/download/CElegansLab-Windows.zip"

if "seleccion_ids" not in st.session_state:
    st.session_state.seleccion_ids = [0]
    st.session_state.siguiente_seleccion_id = 1
if "grupo_ids" not in st.session_state:
    st.session_state.grupo_ids = []
    st.session_state.siguiente_grupo_id = 0
if "resultado" not in st.session_state:
    st.session_state.resultado = None
if "etapa" not in st.session_state:
    st.session_state.etapa = "cargar"


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


# ================= BARRA LATERAL =================
resultado = st.session_state.resultado

with st.sidebar:
    st.markdown(
        '<div class="brand-block"><div class="brand-row">'
        '<div class="brand-icon">🪱</div>'
        '<div class="brand-name">C. elegans<br>Lab</div>'
        '</div><div class="brand-tag">Morfometría de nematodos</div></div>',
        unsafe_allow_html=True,
    )

    etapas = [
        ("cargar", "1 · Cargar fotos"),
        ("resultados", "2 · Resultados"),
        ("corregir", "3 · Corregir detección"),
        ("exportar", "4 · Exportar"),
    ]
    for clave, etiqueta in etapas:
        activa = st.session_state.etapa == clave
        if st.button(
            etiqueta, key=f"nav_{clave}",
            type="primary" if activa else "secondary",
            disabled=(resultado is None and clave != "cargar"),
        ):
            st.session_state.etapa = clave
            st.rerun()

    if resultado is not None:
        with st.container(border=True):
            st.caption(
                f"**{len(resultado['selecciones'])}** selección(es) · "
                f"**{resultado['total_fotos']}** fotos analizadas"
            )

    st.caption("Versión 1.1.0 · Las fotos se procesan en esta computadora y no se suben a ningún lado.")


def _bloquear_si_sin_resultado():
    if resultado is None:
        st.info("Todavía no analizaste fotos. Volvé a **Cargar fotos** y apretá \"Analizar fotos\" para empezar.")
        if st.button("← Ir a Cargar fotos"):
            st.session_state.etapa = "cargar"
            st.rerun()
        st.stop()


# ================= ETAPA 1: CARGAR =================
if st.session_state.etapa == "cargar":
    _screen_header(
        "Etapa 1 de 4", "Cargá las fotos de tu placa",
        "Cada selección junta las fotos de una misma placa o condición, con el objetivo del microscopio con el que se sacaron. Podés cargar más de una selección antes de analizar.",
    )

    for sid in list(st.session_state.seleccion_ids):
        with st.container(border=True):
            col1, col3 = st.columns([5, 1])
            with col1:
                st.text_input("Nombre de la selección", value=f"Selección {sid + 1}", key=f"nombre_{sid}")
            with col3:
                st.write("")
                if len(st.session_state.seleccion_ids) > 1:
                    if st.button("🗑 Eliminar", key=f"quitar_sel_{sid}"):
                        st.session_state.seleccion_ids.remove(sid)
                        st.rerun()

            st.markdown('<div class="tile-label" style="margin-bottom:6px">Objetivo del microscopio</div>', unsafe_allow_html=True)
            objetivo_actual = st.session_state.get(f"objetivo_{sid}", OBJETIVO_POR_DEFECTO)
            cols_obj = st.columns(len(OPCIONES_OBJETIVO) + 4)
            for i, opt in enumerate(OPCIONES_OBJETIVO):
                with cols_obj[i]:
                    if st.button(
                        opt, key=f"obj_btn_{sid}_{opt}",
                        type="primary" if opt == objetivo_actual else "secondary",
                        use_container_width=True,
                    ):
                        st.session_state[f"objetivo_{sid}"] = opt
                        st.rerun()
            st.session_state.setdefault(f"objetivo_{sid}", OBJETIVO_POR_DEFECTO)
            st.caption("Calibrado con la regla Motic — define cuántos µm equivale cada píxel.")

            st.file_uploader(
                "Fotos de esta selección",
                type=EXTENSIONES_VALIDAS,
                accept_multiple_files=True,
                key=f"archivos_{sid}",
            )

    col_add, col_hint = st.columns([1, 2.4])
    with col_add:
        if st.button("➕ Agregar otra selección"):
            st.session_state.seleccion_ids.append(st.session_state.siguiente_seleccion_id)
            st.session_state.siguiente_seleccion_id += 1
            st.rerun()
    with col_hint:
        st.caption("¿Dos selecciones son réplicas de la misma condición? Después las podés agrupar para promediarlas.")

    st.markdown('<h2 style="font-size:1.15rem;margin-top:28px">Promediar entre selecciones (opcional)</h2>', unsafe_allow_html=True)
    st.caption("¿Dos o más selecciones son réplicas de la misma condición y hay que promediarlas entre sí? El promedio del grupo es el promedio de los promedios de cada selección incluida.")

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
    st.markdown("<div style='margin-top:26px'></div>", unsafe_allow_html=True)
    col_sp, col_cta = st.columns([3, 1])
    with col_cta:
        procesar = st.button("▶️ Analizar fotos →", type="primary", disabled=not hay_fotos, use_container_width=True)
    if not hay_fotos:
        st.caption("Subí las fotos en al menos una selección para poder analizar.")

    if procesar:
        carpeta_entrada_raiz = tempfile.mkdtemp(prefix="celab_entrada_")
        carpeta_salida_raiz = tempfile.mkdtemp(prefix="celab_resultados_")

        selecciones_resultado = {}
        errores_totales = []
        total_fotos = 0

        with st.spinner("Analizando fotos, puede tardar un momento..."):
            for sid in st.session_state.seleccion_ids:
                nombre_sel = st.session_state.get(f"nombre_{sid}", f"Selección {sid + 1}")
                objetivo_sel = st.session_state.get(f"objetivo_{sid}", OBJETIVO_POR_DEFECTO)
                px_per_mm_sel = OBJETIVOS_CALIBRADOS[objetivo_sel]
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
                        res = measure_worms(ruta_entrada, salida_img, px_per_mm=px_per_mm_sel)
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
                    "objetivo": objetivo_sel,
                    "px_per_mm": px_per_mm_sel,
                    "filas": filas,
                    "carpeta_entrada": carpeta_entrada,
                    "carpeta_salida": carpeta_salida,
                }

        st.session_state.resultado = {
            "selecciones": selecciones_resultado,
            "total_fotos": total_fotos,
            "errores": errores_totales,
        }
        st.session_state.etapa = "resultados"
        st.rerun()


# ================= ETAPA 2: RESULTADOS =================
elif st.session_state.etapa == "resultados":
    _bloquear_si_sin_resultado()
    _screen_header(
        "Etapa 2 de 4", "Resultados de tus selecciones",
        "Así quedaron medidos tus gusanos. Los verdes se midieron solos; los que dicen \"revisar\" necesitan que los mires en el microscopio o los ajustes en la etapa de corrección.",
    )

    st.success(f"✔ {resultado['total_fotos']} fotos analizadas en {len(resultado['selecciones'])} selección(es).")

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

    if grupos_actuales:
        st.markdown('<h2 style="font-size:1.1rem;margin:10px 0 12px">Promedios por grupo</h2>', unsafe_allow_html=True)
        for grupo in grupos_actuales:
            with st.container(border=True):
                st.markdown(f"**{grupo['nombre']}** — selecciones: {', '.join(n for n, _, _ in grupo['detalle']) or '(ninguna)'}")
                c1, c2 = st.columns(2)
                c1.metric("Área promedio (µm²)", _num_ar(grupo["promedio_area"], 1) if grupo["promedio_area"] is not None else "sin datos")
                c2.metric("Longitud promedio (µm)", _num_ar(grupo["promedio_length"], 1) if grupo["promedio_length"] is not None else "sin datos")

    total_revisar_global = 0

    for sid, sel in resultado["selecciones"].items():
        st.divider()
        st.markdown(f'<h2 style="font-size:1.25rem;margin-bottom:2px">{sel["nombre"]}</h2>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="context-bar"><strong>{sel["nombre"]}</strong> · objetivo {sel.get("objetivo", OBJETIVO_POR_DEFECTO)} · '
            f'{len(dict.fromkeys(f["archivo"] for f in sel["filas"]))} fotos</div>',
            unsafe_allow_html=True,
        )

        area, length, n = calcular_promedio(sel["filas"])
        total = len(sel["filas"])
        revisar = sum(1 for f in sel["filas"] if f["revisar_manualmente"])
        total_revisar_global += revisar

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(_tile_html("Longitud promedio", _num_ar(length, 0) if length is not None else "—", "µm", "Referencia adulto: 1.000–1.100 µm"), unsafe_allow_html=True)
        with c2:
            st.markdown(_tile_html("Área promedio", _num_ar(area, 0) if area is not None else "—", "µm²", "Sobre los gusanos confiables"), unsafe_allow_html=True)
        with c3:
            st.markdown(_tile_html("Medidos automáticamente", str(total - revisar), f"de {total}", "No necesitan revisión", "ok"), unsafe_allow_html=True)
        with c4:
            st.markdown(_tile_html("Para revisar a mano", str(revisar), f"de {total}", "Gusanos cruzados o en el borde", "warn" if revisar else ""), unsafe_allow_html=True)

        svg_escala = _svg_escala_referencia(sel["filas"])
        if svg_escala:
            st.markdown('<div style="margin-top:14px">', unsafe_allow_html=True)
            st.markdown(
                '<div class="scale-legend"><span><span class="dot" style="background:#1F8A5F"></span>Medido automáticamente</span>'
                '<span><span class="dot" style="background:#9A5B00"></span>Para revisar</span></div>',
                unsafe_allow_html=True,
            )
            st.markdown(svg_escala, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        archivos_unicos = list(dict.fromkeys(f["archivo"] for f in sel["filas"]))
        st.markdown('<h3 style="font-size:1rem;margin:22px 0 10px">Fotos analizadas</h3>', unsafe_allow_html=True)
        cols = st.columns(3)
        for i, archivo in enumerate(archivos_unicos):
            ruta_anotada = os.path.join(sel["carpeta_salida"], f"anotada_{archivo}")
            if os.path.exists(ruta_anotada):
                img = cv2.imread(ruta_anotada)
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                n_foto = sum(1 for f in sel["filas"] if f["archivo"] == archivo and f.get("id") is not None)
                n_revisar_foto = sum(1 for f in sel["filas"] if f["archivo"] == archivo and f["revisar_manualmente"])
                with cols[i % 3]:
                    with st.container(border=True):
                        st.image(img_rgb, use_column_width=True)
                        etiqueta = f"{archivo} · {n_foto} gusano(s)"
                        if n_revisar_foto:
                            etiqueta += f" · {n_revisar_foto} para revisar"
                        st.caption(etiqueta)

        st.markdown('<h3 style="font-size:1rem;margin:22px 0 6px">Detalle por gusano</h3>', unsafe_allow_html=True)
        st.caption("Podés editar el área, la longitud, y destildar \"Revisar a mano\" una vez que lo chequeaste en Motic.")

        filas_tabla = [dict(f) for f in sel["filas"]]
        for f in filas_tabla:
            f["estado"] = "🟠 Revisar" if f["revisar_manualmente"] else "🟢 Automático"
        columnas_orden = ["archivo", "id", "estado", "area_um2", "length_um", "revisar_manualmente", "motivo"]
        df_visible = pd.DataFrame(filas_tabla)[columnas_orden] if filas_tabla else pd.DataFrame(columns=columnas_orden)

        editado = st.data_editor(
            df_visible,
            key=f"editor_{sid}",
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            disabled=["archivo", "id", "estado"],
            column_config={
                "archivo": st.column_config.TextColumn("Archivo"),
                "id": st.column_config.NumberColumn("ID"),
                "estado": st.column_config.TextColumn("Estado"),
                "area_um2": st.column_config.NumberColumn("Área (µm²)", format="%.0f"),
                "length_um": st.column_config.NumberColumn("Longitud (µm)", format="%.0f"),
                "revisar_manualmente": st.column_config.CheckboxColumn("Revisar a mano"),
                "motivo": st.column_config.TextColumn("Motivo"),
            },
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

    st.divider()
    col_sp, col_cta = st.columns([3, 1.3])
    with col_cta:
        if st.button(f"Corregir detecciones pendientes ({total_revisar_global}) →", type="primary", use_container_width=True, disabled=total_revisar_global == 0):
            st.session_state.etapa = "corregir"
            st.rerun()


# ================= ETAPA 3: CORREGIR =================
elif st.session_state.etapa == "corregir":
    _bloquear_si_sin_resultado()
    _screen_header(
        "Etapa 3 de 4", "Corregí una detección",
        "Elegí un gusano y ajustá su contorno a mano. Al aplicar la corrección se recalculan el área y la longitud, y se destilda \"revisar manualmente\".",
    )

    sids_con_datos = [sid for sid, sel in resultado["selecciones"].items() if any(f.get("contorno") for f in sel["filas"])]
    if not sids_con_datos:
        st.info("Todavía no hay gusanos detectados para corregir.")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            sid_corr = st.selectbox("Selección", sids_con_datos, format_func=lambda sid: resultado["selecciones"][sid]["nombre"], key="corr_sid")
        sel_corr = resultado["selecciones"][sid_corr]
        archivos_con_datos = list(dict.fromkeys(f["archivo"] for f in sel_corr["filas"] if f.get("contorno")))
        with col2:
            archivo_corr = st.selectbox("Foto", archivos_con_datos, key="corr_archivo")
        if "_pendiente_corr_idx" in st.session_state:
            st.session_state["corr_idx"] = st.session_state.pop("_pendiente_corr_idx")
        filas_de_foto = [(i, f) for i, f in enumerate(sel_corr["filas"]) if f["archivo"] == archivo_corr and f.get("contorno")]
        with col3:
            idx_corr = st.selectbox(
                "Gusano",
                [i for i, _ in filas_de_foto],
                format_func=lambda i: f"#{sel_corr['filas'][i]['id']} (largo={sel_corr['filas'][i]['length_um']}µm, área={sel_corr['filas'][i]['area_um2']}µm²)",
                key="corr_idx",
            )

        fila_corr = sel_corr["filas"][idx_corr]
        px_per_mm_corr = sel_corr.get("px_per_mm") or OBJETIVOS_CALIBRADOS[OBJETIVO_POR_DEFECTO]
        ruta_original = os.path.join(sel_corr["carpeta_entrada"], archivo_corr)
        img_original = cv2.imread(ruta_original)
        img_h, img_w = img_original.shape[:2]

        motivo_actual = fila_corr.get("motivo") or "—"
        st.markdown(
            f'<div class="context-bar">Editando <strong>{archivo_corr} — gusano #{fila_corr["id"]}</strong> · {motivo_actual}</div>',
            unsafe_allow_html=True,
        )

        col_canvas, col_panel = st.columns([1.4, 1])

        with col_panel:
            st.markdown(
                '<ol class="steps-list">'
                '<li><span class="n">1</span>Hacé clic sobre la línea para agregar un punto nuevo.</li>'
                '<li><span class="n">2</span>Arrastrá un punto para moverlo, o su manija celeste para ajustar la curva — se actualiza en vivo.</li>'
                '<li><span class="n">3</span>Hacé clic en un punto sin arrastrar para curvarlo o eliminarlo.</li>'
                '</ol>',
                unsafe_allow_html=True,
            )
            st.caption("¿Esta detección son en realidad 2 gusanos pegados o cruzados? Separala en 2 y después ajustá cada contorno por separado.")
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
        # manejables, con manijas de curvatura por punto, ya curvado por
        # defecto contra el contorno real detectado); "contorno" es el de alta
        # resolución, usado para dibujar y medir.
        contorno_control_guardado = fila_corr.get("contorno_control") or []
        if contorno_control_guardado and isinstance(contorno_control_guardado[0], dict):
            contorno_inicial = contorno_control_guardado
        else:
            # Defensivo: no debería pasar, measure_worms ya guarda el formato rico.
            base = contorno_control_guardado or fila_corr["contorno"]
            contorno_inicial = [{"x": px, "y": py, "curved": False, "hx": 0, "hy": 0} for px, py in base]

        xs = [p["x"] for p in contorno_inicial]
        ys = [p["y"] for p in contorno_inicial]
        margen = 40
        x0 = int(max(0, min(xs) - margen))
        y0 = int(max(0, min(ys) - margen))
        x1 = int(min(img_w, max(xs) + margen))
        y1 = int(min(img_h, max(ys) + margen))

        crop = cv2.cvtColor(img_original[y0:y1, x0:x1], cv2.COLOR_BGR2RGB)
        crop_h, crop_w = crop.shape[:2]

        objetivo_px = 560
        escala = min(3.5, max(1.0, objetivo_px / max(crop_w, crop_h)))
        canvas_w, canvas_h = int(crop_w * escala), int(crop_h * escala)

        crop_img = Image.fromarray(crop).resize((canvas_w, canvas_h))
        puntos_canvas = [
            {
                "x": (p["x"] - x0) * escala, "y": (p["y"] - y0) * escala,
                "curved": p["curved"], "hx": p["hx"] * escala, "hy": p["hy"] * escala,
            }
            for p in contorno_inicial
        ]

        with col_canvas:
            pen_key = f"pen_{sid_corr}_{archivo_corr}_{idx_corr}_v{st.session_state[version_key]}"
            resultado_pen = pen_editor(_imagen_a_data_uri(crop_img), canvas_w, canvas_h, puntos_canvas, key=pen_key)
            st.markdown(
                '<div class="scale-legend"><span><span class="dot" style="background:#7C4FE0"></span>Punto del contorno</span>'
                '<span><span class="dot" style="background:#6636C8;border-radius:2px"></span>Manija de curva</span></div>',
                unsafe_allow_html=True,
            )

        with col_panel:
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
                medicion = medir_desde_contorno(nuevo_control, img_original.shape, px_per_mm_corr)
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


# ================= ETAPA 4: EXPORTAR =================
elif st.session_state.etapa == "exportar":
    _bloquear_si_sin_resultado()
    _screen_header(
        "Etapa 4 de 4", "Exportá tus mediciones",
        "Bajá el Excel con todas las selecciones y sus promedios, o las fotos anotadas de una selección puntual.",
    )

    total_gusanos = sum(len(sel["filas"]) for sel in resultado["selecciones"].values())
    total_revisar = sum(sum(1 for f in sel["filas"] if f["revisar_manualmente"]) for sel in resultado["selecciones"].values())
    with st.container(border=True):
        st.markdown(
            f'##### ✅ Todo listo\n{resultado["total_fotos"]} fotos · {total_gusanos} gusanos medidos · '
            f'{total_gusanos - total_revisar} automáticos · {total_revisar} revisados a mano'
        )

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
        selecciones_para_excel.append({"nombre": sel["nombre"], "objetivo": sel.get("objetivo"), "filas": sel["filas"],
                                        "promedio_area": area, "promedio_length": length, "n": n})

    excel_buffer_path = os.path.join(tempfile.gettempdir(), "celegans_lab_mediciones.xlsx")
    generar_excel(selecciones_para_excel, grupos_actuales, excel_buffer_path)

    st.markdown('<h2 style="font-size:1.1rem;margin:24px 0 12px">Descargas</h2>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown("**Excel con todas las selecciones**")
            st.caption("Cada selección en su sección, con promedios y, si armaste grupos, el promedio entre selecciones.")
            st.markdown('<span class="export-file">mediciones_c_elegans.xlsx</span>', unsafe_allow_html=True)
            with open(excel_buffer_path, "rb") as f:
                st.download_button("⬇️ Descargar Excel", f, file_name="mediciones_c_elegans.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    type="primary", use_container_width=True)
    with col2:
        with st.container(border=True):
            st.markdown("**Fotos anotadas**")
            st.caption("Elegí una selección para descargar sus fotos con los contornos detectados dibujados encima.")
            sid_zip = st.selectbox("Selección", list(resultado["selecciones"].keys()),
                                    format_func=lambda sid: resultado["selecciones"][sid]["nombre"], key="zip_sid")
            sel_zip = resultado["selecciones"][sid_zip]
            st.markdown(f'<span class="export-file">fotos_analizadas_{sel_zip["nombre"]}.zip</span>', unsafe_allow_html=True)
            zip_buffer = zip_de_carpeta(sel_zip["carpeta_salida"])
            st.download_button(f"⬇️ Descargar fotos de \"{sel_zip['nombre']}\"", zip_buffer,
                                file_name=f"fotos_analizadas_{sel_zip['nombre']}.zip", mime="application/zip",
                                key=f"zip_dl_{sid_zip}", use_container_width=True)

    st.markdown('<h2 style="font-size:1.1rem;margin:26px 0 12px">¿Preferís usarlo sin el navegador?</h2>', unsafe_allow_html=True)
    with st.container(border=True):
        col_txt, col_btn = st.columns([3, 1])
        with col_txt:
            st.markdown("**Programa para tu computadora**")
            st.caption("Corre local, sin depender de esta página, y avisa solo cuando hay una versión nueva.")
        with col_btn:
            st.link_button("⬇️ Descargar para PC", URL_DESCARGA_PC, type="primary", use_container_width=True)
