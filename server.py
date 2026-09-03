"""
C. elegans Lab — servidor web (FastAPI + plantillas server-side). Reemplaza
la interfaz Streamlit por HTML/CSS propio, con control total del diseño.
Toda la lógica de detección/medición vive en measure_worms.py, sin cambios.
"""
import copy
import io
import os
import sys
import zipfile

import cv2
from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import state
from measure_worms import (
    OBJETIVO_POR_DEFECTO,
    OBJETIVOS_CALIBRADOS,
    dibujar_overlay,
    medir_desde_contorno,
    measure_worms,
)
from reporte_excel import generar_excel

BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
EXTENSIONES_VALIDAS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
URL_DESCARGA_PC = "https://github.com/fedebianchi22/worm-analysis/releases/latest/download/CElegansLab-Windows.zip"
VERSION = open(os.path.join(BASE_DIR, "VERSION")).read().strip() if os.path.exists(os.path.join(BASE_DIR, "VERSION")) else "-"

app = FastAPI(title="C. elegans Lab")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
templates.env.globals["OPCIONES_OBJETIVO"] = list(OBJETIVOS_CALIBRADOS.keys())
templates.env.globals["VERSION"] = VERSION


# ================= Sesión =================

def _sesion(request: Request):
    cookie_id = request.cookies.get(state.COOKIE_NAME)
    return state.obtener_sesion(cookie_id)


def _con_cookie(response, sid):
    response.set_cookie(state.COOKIE_NAME, sid, httponly=True, samesite="lax", max_age=state.TTL_SEGUNDOS)
    return response


def _redirigir(url, sid):
    return _con_cookie(RedirectResponse(url=url, status_code=303), sid)


def _render(request, sid, plantilla, contexto):
    resp = templates.TemplateResponse(request, plantilla, contexto)
    return _con_cookie(resp, sid)


# ================= Helpers de cálculo (idénticos a la versión anterior) =================

def calcular_promedio(filas):
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


def _num_ar(valor, decimales=0):
    if valor is None:
        return "—"
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "@").replace(".", ",").replace("@", ".")


def _svg_escala_referencia(filas):
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

    svg = banda(200, 300, "var(--surface-3)") + banda(300, 950, "var(--surface-2)") + banda(1000, 1100, "var(--accent-soft)")
    svg += (
        f'<text x="{x(250):.1f}" y="24" text-anchor="middle" class="svg-label">L1</text>'
        f'<text x="{x(625):.1f}" y="24" text-anchor="middle" class="svg-label">L2-L4</text>'
        f'<text x="{x(1050):.1f}" y="24" text-anchor="middle" class="svg-label svg-label-accent">Adulto</text>'
    )
    for tv in [0, 250, 500, 750, 1000, escala_max]:
        xt = x(tv)
        etiqueta = _num_ar(tv) + (" µm" if tv == escala_max else "")
        svg += (
            f'<line x1="{xt:.1f}" y1="76" x2="{xt:.1f}" y2="82" class="svg-tick"/>'
            f'<text x="{xt:.1f}" y="96" text-anchor="middle" class="svg-label">{etiqueta}</text>'
        )
    svg += f'<line x1="{margen_izq}" y1="76" x2="{margen_izq + ancho_plot}" y2="76" class="svg-tick"/>'
    for i, (valor, revisar) in enumerate(valores):
        cx = x(valor)
        cy = 66 if i % 2 == 0 else 82
        clase = "svg-dot-warn" if revisar else "svg-dot-ok"
        svg += f'<circle cx="{cx:.1f}" cy="{cy}" r="5.5" class="{clase}"/>'
    return f'<svg viewBox="0 0 800 118" width="100%" height="118" role="img" aria-label="Longitud de cada gusano contra los rangos de referencia por estadio">{svg}</svg>'


def zip_de_carpeta_bytes(carpeta, prefijo="anotada_"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for nombre in sorted(os.listdir(carpeta)):
            if nombre.startswith(prefijo):
                zf.write(os.path.join(carpeta, nombre), arcname=nombre)
    buffer.seek(0)
    return buffer


def _contexto_sidebar(sesion):
    resultado = sesion["resultado"]
    return {
        "hay_resultado": resultado is not None,
        "resumen_sidebar": (
            f"{len(resultado['selecciones'])} selección(es) · {resultado['total_fotos']} fotos analizadas"
            if resultado else None
        ),
    }


# ================= Raíz =================

@app.get("/")
def raiz(request: Request):
    sid, _ = _sesion(request)
    return _redirigir("/cargar", sid)


# ================= Etapa 1: cargar =================

@app.get("/cargar")
def pagina_cargar(request: Request):
    sid, sesion = _sesion(request)
    ctx = {
        "etapa": "cargar",
        "selecciones": sesion["selecciones"],
        "grupos": sesion["grupos"],
        "nombres_actuales": {s: d["nombre"] for s, d in sesion["selecciones"].items()},
        "hay_fotos": any(d["archivos"] for d in sesion["selecciones"].values()),
        **_contexto_sidebar(sesion),
    }
    return _render(request, sid, "cargar.html", ctx)


@app.post("/cargar/agregar-seleccion")
def agregar_seleccion(request: Request):
    sid, sesion = _sesion(request)
    nuevo = sesion["siguiente_sid"]
    sesion["selecciones"][nuevo] = {"nombre": f"Selección {nuevo + 1}", "objetivo": OBJETIVO_POR_DEFECTO, "archivos": []}
    sesion["siguiente_sid"] += 1
    return _redirigir("/cargar", sid)


@app.post("/cargar/{sel_id}/eliminar")
def eliminar_seleccion(request: Request, sel_id: int):
    sid, sesion = _sesion(request)
    if len(sesion["selecciones"]) > 1:
        sesion["selecciones"].pop(sel_id, None)
    return _redirigir("/cargar", sid)


@app.post("/cargar/{sel_id}/nombre")
def actualizar_nombre(request: Request, sel_id: int, nombre: str = Form(...)):
    sid, sesion = _sesion(request)
    if sel_id in sesion["selecciones"]:
        sesion["selecciones"][sel_id]["nombre"] = nombre.strip() or f"Selección {sel_id + 1}"
    return _redirigir("/cargar", sid)


@app.post("/cargar/{sel_id}/objetivo")
def actualizar_objetivo(request: Request, sel_id: int, objetivo: str = Form(...)):
    sid, sesion = _sesion(request)
    if sel_id in sesion["selecciones"] and objetivo in OBJETIVOS_CALIBRADOS:
        sesion["selecciones"][sel_id]["objetivo"] = objetivo
    return _redirigir("/cargar", sid)


@app.post("/cargar/{sel_id}/fotos")
async def subir_fotos(request: Request, sel_id: int, fotos: list[UploadFile] = None):
    sid, sesion = _sesion(request)
    sel = sesion["selecciones"].get(sel_id)
    if sel is not None and fotos:
        carpeta = os.path.join(sesion["carpeta"], "entrada", str(sel_id))
        os.makedirs(carpeta, exist_ok=True)
        for archivo in fotos:
            nombre = os.path.basename(archivo.filename or "")
            ext = os.path.splitext(nombre)[1].lower()
            if not nombre or ext not in EXTENSIONES_VALIDAS:
                continue
            ruta = os.path.join(carpeta, nombre)
            contenido = await archivo.read()
            with open(ruta, "wb") as f:
                f.write(contenido)
            sel["archivos"] = [a for a in sel["archivos"] if a["nombre"] != nombre]
            sel["archivos"].append({"nombre": nombre, "ruta": ruta, "tamano": len(contenido)})
    return _redirigir("/cargar", sid)


@app.post("/cargar/{sel_id}/fotos/eliminar")
def eliminar_foto(request: Request, sel_id: int, nombre: str = Form(...)):
    sid, sesion = _sesion(request)
    sel = sesion["selecciones"].get(sel_id)
    if sel is not None:
        sel["archivos"] = [a for a in sel["archivos"] if a["nombre"] != nombre]
    return _redirigir("/cargar", sid)


@app.post("/cargar/grupos/agregar")
def agregar_grupo(request: Request):
    sid, sesion = _sesion(request)
    nuevo = sesion["siguiente_gid"]
    sesion["grupos"][nuevo] = {"nombre": f"Grupo {nuevo + 1}", "sids": []}
    sesion["siguiente_gid"] += 1
    return _redirigir("/cargar", sid)


@app.post("/cargar/grupos/{gid}/eliminar")
def eliminar_grupo(request: Request, gid: int):
    sid, sesion = _sesion(request)
    sesion["grupos"].pop(gid, None)
    return _redirigir("/cargar", sid)


@app.post("/cargar/grupos/{gid}/nombre")
def actualizar_nombre_grupo(request: Request, gid: int, nombre: str = Form(...)):
    sid, sesion = _sesion(request)
    if gid in sesion["grupos"]:
        sesion["grupos"][gid]["nombre"] = nombre.strip() or f"Grupo {gid + 1}"
    return _redirigir("/cargar", sid)


@app.post("/cargar/grupos/{gid}/selecciones")
async def actualizar_selecciones_grupo(request: Request, gid: int):
    sid, sesion = _sesion(request)
    form = await request.form()
    sids = [int(v) for v in form.getlist("sids")]
    if gid in sesion["grupos"]:
        sesion["grupos"][gid]["sids"] = sids
    return _redirigir("/cargar", sid)


@app.post("/analizar")
def analizar(request: Request):
    sid, sesion = _sesion(request)
    carpeta_salida_raiz = os.path.join(sesion["carpeta"], "salida")

    selecciones_resultado = {}
    errores_totales = []
    total_fotos = 0

    for sel_id, sel in sesion["selecciones"].items():
        if not sel["archivos"]:
            continue
        objetivo_sel = sel["objetivo"] or OBJETIVO_POR_DEFECTO
        px_per_mm_sel = OBJETIVOS_CALIBRADOS[objetivo_sel]
        carpeta_entrada = os.path.join(sesion["carpeta"], "entrada", str(sel_id))
        carpeta_salida = os.path.join(carpeta_salida_raiz, str(sel_id))
        os.makedirs(carpeta_salida, exist_ok=True)

        filas = []
        for archivo in sel["archivos"]:
            nombre_archivo = archivo["nombre"]
            salida_img = os.path.join(carpeta_salida, f"anotada_{nombre_archivo}")
            try:
                res = measure_worms(archivo["ruta"], salida_img, px_per_mm=px_per_mm_sel)
                if not res:
                    filas.append({"archivo": nombre_archivo, "id": None, "area_um2": None,
                                   "length_um": None, "revisar_manualmente": True,
                                   "motivo": "no se detectó ningún gusano"})
                for r in res:
                    filas.append({"archivo": nombre_archivo, **r})
            except Exception as e:
                errores_totales.append(f"[{sel['nombre']}] {nombre_archivo}: {e}")
            total_fotos += 1

        selecciones_resultado[sel_id] = {
            "nombre": sel["nombre"],
            "objetivo": objetivo_sel,
            "px_per_mm": px_per_mm_sel,
            "filas": filas,
            "carpeta_entrada": carpeta_entrada,
            "carpeta_salida": carpeta_salida,
        }

    sesion["resultado"] = {
        "selecciones": selecciones_resultado,
        "total_fotos": total_fotos,
        "errores": errores_totales,
    }
    return _redirigir("/resultados", sid)


# ================= Etapa 2: resultados =================

@app.get("/resultados")
def pagina_resultados(request: Request):
    sid, sesion = _sesion(request)
    resultado = sesion["resultado"]
    if resultado is None:
        return _redirigir("/cargar", sid)

    grupos_actuales = []
    for gid, grupo in sesion["grupos"].items():
        detalle, area_grupo, length_grupo = calcular_promedio_grupo(grupo["sids"], resultado["selecciones"])
        grupos_actuales.append({"nombre": grupo["nombre"], "detalle": detalle,
                                 "promedio_area": area_grupo, "promedio_length": length_grupo})

    secciones = []
    total_revisar_global = 0
    for sel_id, sel in resultado["selecciones"].items():
        area, length, n = calcular_promedio(sel["filas"])
        total = len(sel["filas"])
        revisar = sum(1 for f in sel["filas"] if f["revisar_manualmente"])
        total_revisar_global += revisar

        archivos_unicos = list(dict.fromkeys(f["archivo"] for f in sel["filas"]))
        fotos = []
        for archivo in archivos_unicos:
            ruta_anotada = os.path.join(sel["carpeta_salida"], f"anotada_{archivo}")
            if os.path.exists(ruta_anotada):
                n_foto = sum(1 for f in sel["filas"] if f["archivo"] == archivo and f.get("id") is not None)
                n_revisar_foto = sum(1 for f in sel["filas"] if f["archivo"] == archivo and f["revisar_manualmente"])
                fotos.append({"archivo": archivo, "sel_id": sel_id, "n": n_foto, "n_revisar": n_revisar_foto})

        secciones.append({
            "sel_id": sel_id, "nombre": sel["nombre"], "objetivo": sel["objetivo"],
            "n_fotos": len(archivos_unicos), "area": area, "length": length,
            "total": total, "revisar": revisar,
            "svg_escala": _svg_escala_referencia(sel["filas"]),
            "fotos": fotos,
            "filas": list(enumerate(sel["filas"])),
        })

    ctx = {
        "etapa": "resultados",
        "resultado": resultado,
        "grupos_actuales": grupos_actuales,
        "secciones": secciones,
        "total_revisar_global": total_revisar_global,
        "num": _num_ar,
        **_contexto_sidebar(sesion),
    }
    return _render(request, sid, "resultados.html", ctx)


@app.post("/resultados/{sel_id}/guardar")
async def guardar_tabla(request: Request, sel_id: int):
    sid, sesion = _sesion(request)
    resultado = sesion["resultado"]
    if resultado is None or sel_id not in resultado["selecciones"]:
        return _redirigir("/resultados", sid)
    form = await request.form()
    filas = resultado["selecciones"][sel_id]["filas"]
    for i, fila in enumerate(filas):
        area = form.get(f"area_{i}")
        length = form.get(f"length_{i}")
        if area not in (None, ""):
            fila["area_um2"] = float(area)
        if length not in (None, ""):
            fila["length_um"] = float(length)
        fila["revisar_manualmente"] = form.get(f"revisar_{i}") == "on"
        fila["motivo"] = form.get(f"motivo_{i}", fila.get("motivo", ""))
    return _redirigir("/resultados", sid)


@app.get("/foto/{sel_id}/{archivo}")
def servir_foto_anotada(request: Request, sel_id: int, archivo: str):
    _, sesion = _sesion(request)
    resultado = sesion["resultado"]
    if resultado is None or sel_id not in resultado["selecciones"]:
        return RedirectResponse("/cargar")
    ruta = os.path.join(resultado["selecciones"][sel_id]["carpeta_salida"], f"anotada_{os.path.basename(archivo)}")
    return FileResponse(ruta)


# ================= Etapa 3: corregir =================

def _imagen_a_data_uri(ruta):
    import base64
    with open(ruta, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")


@app.get("/corregir")
def pagina_corregir(request: Request, sid_sel: int = None, archivo: str = None, idx: int = None):
    sid, sesion = _sesion(request)
    resultado = sesion["resultado"]
    if resultado is None:
        return _redirigir("/cargar", sid)

    sids_con_datos = [s for s, sel in resultado["selecciones"].items() if any(f.get("contorno") for f in sel["filas"])]
    if not sids_con_datos:
        return _render(request, sid, "corregir.html", {"etapa": "corregir", "sin_datos": True, **_contexto_sidebar(sesion)})

    if sid_sel is None or sid_sel not in sids_con_datos:
        sid_sel = sids_con_datos[0]
    sel = resultado["selecciones"][sid_sel]
    archivos_con_datos = list(dict.fromkeys(f["archivo"] for f in sel["filas"] if f.get("contorno")))
    if archivo is None or archivo not in archivos_con_datos:
        archivo = archivos_con_datos[0]
    filas_de_foto = [(i, f) for i, f in enumerate(sel["filas"]) if f["archivo"] == archivo and f.get("contorno")]
    indices_validos = [i for i, _ in filas_de_foto]
    if idx is None or idx not in indices_validos:
        idx = indices_validos[0]

    fila_corr = sel["filas"][idx]
    px_per_mm_corr = sel.get("px_per_mm") or OBJETIVOS_CALIBRADOS[OBJETIVO_POR_DEFECTO]
    ruta_original = os.path.join(sel["carpeta_entrada"], archivo)
    img_original = cv2.imread(ruta_original)
    img_h, img_w = img_original.shape[:2]

    contorno_control_guardado = fila_corr.get("contorno_control") or []
    if contorno_control_guardado and isinstance(contorno_control_guardado[0], dict):
        contorno_inicial = contorno_control_guardado
    else:
        base = contorno_control_guardado or fila_corr["contorno"]
        contorno_inicial = [{"x": px, "y": py, "curved": False, "hx": 0, "hy": 0} for px, py in base]

    xs = [p["x"] for p in contorno_inicial]
    ys = [p["y"] for p in contorno_inicial]
    margen = 40
    x0 = int(max(0, min(xs) - margen))
    y0 = int(max(0, min(ys) - margen))
    x1 = int(min(img_w, max(xs) + margen))
    y1 = int(min(img_h, max(ys) + margen))

    crop = img_original[y0:y1, x0:x1]
    crop_h, crop_w = crop.shape[:2]
    objetivo_px = 560
    escala = min(3.5, max(1.0, objetivo_px / max(crop_w, crop_h)))
    canvas_w, canvas_h = int(crop_w * escala), int(crop_h * escala)
    crop_resized = cv2.resize(crop, (canvas_w, canvas_h))
    ruta_crop_tmp = os.path.join(sesion["carpeta"], "_crop_actual.png")
    cv2.imwrite(ruta_crop_tmp, crop_resized)

    puntos_canvas = [
        {"x": (p["x"] - x0) * escala, "y": (p["y"] - y0) * escala,
         "curved": p["curved"], "hx": p["hx"] * escala, "hy": p["hy"] * escala}
        for p in contorno_inicial
    ]

    ctx = {
        "etapa": "corregir",
        "sin_datos": False,
        "selecciones": resultado["selecciones"], "sids_con_datos": sids_con_datos,
        "sid_sel": sid_sel, "archivo": archivo, "idx": idx,
        "archivos_con_datos": archivos_con_datos, "indices_validos": indices_validos, "filas_de_foto": filas_de_foto,
        "fila_corr": fila_corr, "motivo_actual": fila_corr.get("motivo") or "—",
        "imagen_data_uri": _imagen_a_data_uri(ruta_crop_tmp),
        "canvas_w": canvas_w, "canvas_h": canvas_h,
        "puntos_canvas_json": __import__("json").dumps(puntos_canvas),
        "escala": escala, "x0": x0, "y0": y0,
        "puede_separar": len(sel["filas"]) >= 1,
        **_contexto_sidebar(sesion),
    }
    return _render(request, sid, "corregir.html", ctx)


@app.post("/corregir/separar")
def separar_gusano(request: Request, sid_sel: int = Form(...), archivo: str = Form(...), idx: int = Form(...)):
    sid, sesion = _sesion(request)
    resultado = sesion["resultado"]
    sel = resultado["selecciones"][sid_sel]
    fila_corr = sel["filas"][idx]

    ids_existentes = [f["id"] for f in sel["filas"] if f.get("id") is not None]
    siguiente_id = (max(ids_existentes) + 1) if ids_existentes else 0

    fila_a = copy.deepcopy(fila_corr)
    fila_a["id"] = siguiente_id
    fila_a["motivo"] = "dividido de una detección conjunta - falta ajustar el contorno"
    fila_a["revisar_manualmente"] = True

    fila_b = copy.deepcopy(fila_corr)
    fila_b["id"] = siguiente_id + 1
    fila_b["motivo"] = "dividido de una detección conjunta - falta ajustar el contorno"
    fila_b["revisar_manualmente"] = True

    sel["filas"][idx:idx + 1] = [fila_a, fila_b]

    gusanos_de_la_foto = [f for f in sel["filas"] if f["archivo"] == archivo and f.get("contorno")]
    ruta_original = os.path.join(sel["carpeta_entrada"], archivo)
    ruta_salida = os.path.join(sel["carpeta_salida"], f"anotada_{archivo}")
    dibujar_overlay(ruta_original, ruta_salida, gusanos_de_la_foto)

    return _redirigir(f"/corregir?sid_sel={sid_sel}&archivo={archivo}&idx={idx}", sid)


@app.post("/corregir/aplicar")
async def aplicar_correccion(request: Request):
    sid, sesion = _sesion(request)
    form = await request.form()
    sid_sel = int(form["sid_sel"])
    archivo = form["archivo"]
    idx = int(form["idx"])
    import json
    puntos_editados = json.loads(form["puntos"])

    resultado = sesion["resultado"]
    sel = resultado["selecciones"][sid_sel]
    fila_corr = sel["filas"][idx]
    px_per_mm_corr = sel.get("px_per_mm") or OBJETIVOS_CALIBRADOS[OBJETIVO_POR_DEFECTO]
    ruta_original = os.path.join(sel["carpeta_entrada"], archivo)
    img_original = cv2.imread(ruta_original)

    escala = float(form["escala"])
    x0 = int(form["x0"])
    y0 = int(form["y0"])

    if len(puntos_editados) >= 3:
        nuevo_control = [
            {"x": x0 + p["x"] / escala, "y": y0 + p["y"] / escala,
             "curved": p["curved"], "hx": p["hx"] / escala, "hy": p["hy"] / escala}
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

        gusanos_de_la_foto = [f for f in sel["filas"] if f["archivo"] == archivo and f.get("contorno")]
        ruta_salida = os.path.join(sel["carpeta_salida"], f"anotada_{archivo}")
        dibujar_overlay(ruta_original, ruta_salida, gusanos_de_la_foto)

    return _redirigir(f"/corregir?sid_sel={sid_sel}&archivo={archivo}&idx={idx}", sid)


# ================= Etapa 4: exportar =================

@app.get("/exportar")
def pagina_exportar(request: Request):
    sid, sesion = _sesion(request)
    resultado = sesion["resultado"]
    if resultado is None:
        return _redirigir("/cargar", sid)

    total_gusanos = sum(len(sel["filas"]) for sel in resultado["selecciones"].values())
    total_revisar = sum(sum(1 for f in sel["filas"] if f["revisar_manualmente"]) for sel in resultado["selecciones"].values())

    ctx = {
        "etapa": "exportar",
        "resultado": resultado,
        "total_fotos": resultado["total_fotos"],
        "total_gusanos": total_gusanos,
        "total_revisar": total_revisar,
        "URL_DESCARGA_PC": URL_DESCARGA_PC,
        **_contexto_sidebar(sesion),
    }
    return _render(request, sid, "exportar.html", ctx)


@app.get("/exportar/excel")
def exportar_excel(request: Request):
    _, sesion = _sesion(request)
    resultado = sesion["resultado"]

    grupos_actuales = []
    for gid, grupo in sesion["grupos"].items():
        detalle, area_grupo, length_grupo = calcular_promedio_grupo(grupo["sids"], resultado["selecciones"])
        grupos_actuales.append({"nombre": grupo["nombre"], "detalle": detalle,
                                 "promedio_area": area_grupo, "promedio_length": length_grupo})

    selecciones_para_excel = []
    for sel in resultado["selecciones"].values():
        area, length, n = calcular_promedio(sel["filas"])
        selecciones_para_excel.append({"nombre": sel["nombre"], "objetivo": sel.get("objetivo"), "filas": sel["filas"],
                                        "promedio_area": area, "promedio_length": length, "n": n})

    ruta = os.path.join(sesion["carpeta"], "mediciones_c_elegans.xlsx")
    generar_excel(selecciones_para_excel, grupos_actuales, ruta)
    return FileResponse(ruta, filename="mediciones_c_elegans.xlsx",
                         media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/exportar/zip/{sel_id}")
def exportar_zip(request: Request, sel_id: int):
    _, sesion = _sesion(request)
    resultado = sesion["resultado"]
    sel = resultado["selecciones"][sel_id]
    buffer = zip_de_carpeta_bytes(sel["carpeta_salida"])
    nombre = f"fotos_analizadas_{sel['nombre']}.zip"
    return StreamingResponse(buffer, media_type="application/zip",
                              headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
