"""
Detección y medición automática de gusanos (nematodos) en fotos de microscopio.
Calibración: 393.0 px = 1 mm (objetivo 4X, confirmada con el asistente de calibración de Motic).
"""
import cv2
import numpy as np
from skimage.morphology import skeletonize
import networkx as nx

PX_PER_MM = 393.0  # calibración 4X (del asistente de calibración de Motic: 2.544529 µm/px)
PX_PER_UM = PX_PER_MM / 1000  # píxeles por micrómetro

KERNEL_SUAVE = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))


def _suavizar_mascara(mask):
    # Suavizar bordes chicos del contorno: sin esto, una pequeña irregularidad
    # en el borde puede esqueletizarse como una bifurcación falsa y marcar un
    # gusano normal como "posible cruce" sin que haya ningún cruce real.
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, KERNEL_SUAVE, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, KERNEL_SUAVE, iterations=1)
    return mask


def _esqueletizar(mask):
    """Devuelve (length_px, skel_points, junctions) a partir de una máscara binaria."""
    skeleton = skeletonize(mask > 0)
    ys, xs = np.nonzero(skeleton)
    skel_points = list(zip(xs.tolist(), ys.tolist()))
    skel_set = set(skel_points)

    Gs = nx.Graph()
    for (px_, py_) in skel_points:
        Gs.add_node((px_, py_))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nb = (px_ + dx, py_ + dy)
                if nb in skel_set:
                    Gs.add_edge((px_, py_), nb, weight=np.hypot(dx, dy))

    degrees = dict(Gs.degree())
    junctions = [n for n, d in degrees.items() if d >= 3]
    length_px = sum(data["weight"] for _, _, data in Gs.edges(data=True))
    return length_px, skel_points, junctions


def _simplificar_contorno(cnt, n_objetivo=14, intentos=12):
    """Reduce un contorno (cientos de puntos) a ~n_objetivo puntos manipulables a mano."""
    perimetro = cv2.arcLength(cnt, True)
    if perimetro == 0:
        return cnt.reshape(-1, 2).tolist()

    epsilon = perimetro * 0.01
    aprox = cv2.approxPolyDP(cnt, epsilon, True)
    for _ in range(intentos):
        if len(aprox) <= n_objetivo + 4 and len(aprox) >= max(4, n_objetivo - 6):
            break
        if len(aprox) > n_objetivo:
            epsilon *= 1.3
        else:
            epsilon *= 0.7
        aprox = cv2.approxPolyDP(cnt, epsilon, True)
    return aprox.reshape(-1, 2).tolist()


def _aplanar_trazado(puntos, muestras_por_tramo=14):
    """
    Convierte un contorno cerrado con manijas de curvatura por punto (estilo
    pluma de Photoshop/Illustrator) en un polígono fino, evaluando cada tramo
    como una curva Bezier cúbica. puntos: lista de dicts {x, y, hx, hy} donde
    (hx, hy) es el offset de la manija de salida respecto al punto (0,0 =
    esquina recta; el tramo queda una línea recta automáticamente).
    """
    n = len(puntos)
    if n < 3:
        return [[p["x"], p["y"]] for p in puntos]
    fino = []
    for i in range(n):
        p1, p2 = puntos[i], puntos[(i + 1) % n]
        x1, y1 = p1["x"], p1["y"]
        x2, y2 = p2["x"], p2["y"]
        c1x, c1y = x1 + p1.get("hx", 0), y1 + p1.get("hy", 0)
        c2x, c2y = x2 - p2.get("hx", 0), y2 - p2.get("hy", 0)
        for j in range(muestras_por_tramo):
            t = j / muestras_por_tramo
            mt = 1 - t
            x = mt ** 3 * x1 + 3 * mt ** 2 * t * c1x + 3 * mt * t ** 2 * c2x + t ** 3 * x2
            y = mt ** 3 * y1 + 3 * mt ** 2 * t * c1y + 3 * mt * t ** 2 * c2y + t ** 3 * y2
            fino.append([x, y])
    return fino


def medir_desde_contorno(puntos, img_shape):
    """
    Recalcula área y longitud a partir de un contorno editado a mano.
    puntos: lista de dicts {x, y, curved, hx, hy} (ver _aplanar_trazado). Se
    usa desde el corrector de imagen cuando el usuario ajusta el contorno
    detectado automáticamente, incluyendo tramos curvados por punto.
    """
    fino = _aplanar_trazado(puntos)
    mask = np.zeros(img_shape[:2], dtype=np.uint8)
    pts = np.array([fino], dtype=np.int32)
    cv2.fillPoly(mask, pts, 255)
    mask = _suavizar_mascara(mask)

    area_px = int((mask > 0).sum())
    length_px, skel_points, junctions = _esqueletizar(mask)

    area_um2 = area_px / (PX_PER_UM ** 2)
    length_um = length_px / PX_PER_UM
    return {
        "area_um2": round(area_um2, 1),
        "length_um": round(length_um, 1),
        "skel_points": skel_points,
        "junctions": junctions,
        "posible_cruce": len(junctions) > 0,
        "contorno_dibujo": [[int(round(x)), int(round(y))] for x, y in fino],
    }


def dibujar_overlay(image_path, out_path, gusanos):
    """
    Regenera la imagen anotada completa a partir de la foto original y el
    estado actual (posiblemente corregido a mano) de cada gusano.
    gusanos: lista de dicts con "id", "contorno" (lista de [x,y]),
        "length_um", "revisar_manualmente", "motivo", "skel_points" (opcional).
    """
    img = cv2.imread(image_path)
    overlay = img.copy()

    for g in gusanos:
        pts = np.array([g["contorno"]], dtype=np.int32)
        x, y, w, h = cv2.boundingRect(pts)
        revisar = g["revisar_manualmente"]
        color = (0, 0, 255) if revisar else (0, 255, 0)
        cv2.drawContours(overlay, [pts], -1, color, 2)

        for (px_, py_) in g.get("skel_points", []):
            if 0 <= py_ < overlay.shape[0] and 0 <= px_ < overlay.shape[1]:
                overlay[py_, px_] = (255, 0, 255) if g.get("posible_cruce") else (0, 0, 255)

        motivo = g.get("motivo") or ""
        label = f"REVISAR: {motivo}" if revisar and motivo else ("REVISAR" if revisar else f"L={g['length_um']:.0f}um")
        cv2.putText(overlay, f"#{g['id']} {label}", (x, max(0, y - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 0, 0), 2)

    cv2.imwrite(out_path, overlay)


def measure_worms(image_path, out_path, min_area_px=800, max_area_px=60000, max_solidity=0.65):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Suavizar un poco para reducir ruido de la cámara
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # Corregir el degradado de iluminación (viñeteado hacia los bordes de la foto):
    # estimamos el fondo con un cierre morfológico de kernel grande (más ancho que
    # cualquier gusano, así los "cierra" y deja solo el nivel de fondo local) y
    # aplanamos dividiendo por esa estimación. Sin esto, un gusano tenue en una zona
    # oscurecida por el viñeteado queda fusionado con el fondo y no se detecta.
    kernel_fondo = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (51, 51))
    fondo = cv2.morphologyEx(blur, cv2.MORPH_CLOSE, kernel_fondo)
    corregida = cv2.divide(blur, fondo, scale=255)

    # El gusano es más oscuro que el fondo -> threshold adaptativo
    # Usamos Otsu sobre el negativo para separar objetos oscuros
    _, thresh = cv2.threshold(corregida, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Limpieza morfológica: sacar ruido chico y cerrar huecos en el trazo del gusano
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    clean = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
    clean = cv2.morphologyEx(clean, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    overlay = img.copy()
    results = []
    img_h, img_w = gray.shape

    for i, cnt in enumerate(contours):
        area_px = cv2.contourArea(cnt)
        if area_px < min_area_px or area_px > max_area_px:
            continue  # descarta manchas/ruido chico y sombras/viñeta de fondo

        # Filtrar por forma: un gusano (aunque esté doblado) tiene "solidez" baja
        # (área real / área del casco convexo), a diferencia de sombras o manchas compactas.
        x, y, w, h = cv2.boundingRect(cnt)
        hull = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        solidity = area_px / hull_area if hull_area > 0 else 1.0
        if solidity > max_solidity:
            continue

        # Máscara individual de este contorno para el esqueleto
        mask = np.zeros(gray.shape, dtype=np.uint8)
        cv2.drawContours(mask, [cnt], -1, 255, -1)
        mask = _suavizar_mascara(mask)

        length_px, skel_points, junctions = _esqueletizar(mask)
        posible_cruce = len(junctions) > 0

        area_um2 = area_px / (PX_PER_UM ** 2)
        length_um = length_px / PX_PER_UM

        # Marca si el contorno toca el borde de la imagen: el gusano puede estar
        # cortado y la medición no sería confiable -> se debe revisar a mano.
        touches_border = (x <= 1 or y <= 1 or (x + w) >= img_w - 1 or (y + h) >= img_h - 1)
        revisar = touches_border or posible_cruce

        motivo = []
        if touches_border:
            motivo.append("cortado en el borde")
        if posible_cruce:
            motivo.append("posibles gusanos pegados/cruzados")

        results.append({
            "id": i,
            "area_um2": round(area_um2, 1),
            "length_um": round(length_um, 1),
            "revisar_manualmente": revisar,
            "motivo": "; ".join(motivo) if motivo else "",
            # "contorno" es el de alta resolución (el mismo que se dibuja acá
            # abajo): dibujar_overlay() lo reutiliza para redibujar TODOS los
            # gusanos de la foto cada vez que se corrige uno solo, así que si
            # fuera el simplificado, los gusanos no tocados quedarían con un
            # contorno anguloso en vez de la curva suave original.
            "contorno": cnt.reshape(-1, 2).tolist(),
            # "contorno_control" es el simplificado (pocos puntos), para el
            # editor a mano; se reemplaza por el ajustado por el usuario recién
            # cuando aplica una corrección.
            "contorno_control": _simplificar_contorno(cnt),
            "skel_points": skel_points,
            "posible_cruce": posible_cruce,
        })

        # Dibujar overlay: contorno en verde (ok) o rojo (revisar a mano)
        color = (0, 0, 255) if revisar else (0, 255, 0)
        cv2.drawContours(overlay, [cnt], -1, color, 2)
        for (px_, py_) in skel_points:
            overlay[py_, px_] = (255, 0, 255) if posible_cruce else (0, 0, 255)
        for (px_, py_) in junctions:
            cv2.circle(overlay, (px_, py_), 5, (0, 255, 255), -1)
        label = "REVISAR: " + (", ".join(motivo)) if motivo else f"L={length_um:.0f}um"
        cv2.putText(overlay, f"#{i} {label}", (x, max(0, y - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 0, 0), 2)

    cv2.imwrite(out_path, overlay)
    return results
