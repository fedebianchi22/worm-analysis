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

def measure_worms(image_path, out_path, min_area_px=800, max_area_px=60000, max_solidity=0.65):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Suavizar un poco para reducir ruido de la cámara
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # El gusano es más oscuro que el fondo -> threshold adaptativo
    # Usamos Otsu sobre el negativo para separar objetos oscuros
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

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
        aspect = max(w, h) / max(1, min(w, h))
        hull = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        solidity = area_px / hull_area if hull_area > 0 else 1.0
        if solidity > max_solidity:
            continue

        # Máscara individual de este contorno para el esqueleto
        mask = np.zeros(gray.shape, dtype=np.uint8)
        cv2.drawContours(mask, [cnt], -1, 255, -1)

        skeleton = skeletonize(mask > 0)
        ys, xs = np.nonzero(skeleton)
        skel_points = list(zip(xs, ys))
        skel_set = set(skel_points)

        # Grafo del esqueleto para detectar bifurcaciones (gusanos pegados/cruzados)
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
        posible_cruce = len(junctions) > 0

        # Longitud del esqueleto: sumar distancias entre píxeles conectados por vecindad
        length_px = sum(data["weight"] for _, _, data in Gs.edges(data=True))

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
            "area_um2": None if posible_cruce else round(area_um2, 1),
            "length_um": None if posible_cruce else round(length_um, 1),
            "revisar_manualmente": revisar,
            "motivo": "; ".join(motivo) if motivo else "",
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
