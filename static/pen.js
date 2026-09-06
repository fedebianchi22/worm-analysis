/* Editor de contorno tipo "pluma" (Photoshop). Dibuja sobre un <svg>, sin
   dependencias externas. Se inicializa con CelabPen.iniciar(...) y expone
   CelabPen.puntosActuales() para leer el resultado antes de enviarlo.

   Estilo inspirado en el trazado de Photoshop: línea fina (con un halo
   oscuro debajo para que se vea igual sobre fondos claros u oscuros) y
   anclas chicas cuadradas — el área donde se puede hacer click en cada
   punto es más grande que el cuadradito visual, para que sea fácil de
   agarrar sin que los puntos se vean grandes y se pisen entre sí.

   Las acciones sobre el punto seleccionado (curvar/eliminar) no se
   muestran en un menú flotante sobre el punto -eso tapaba las manijas de
   curva-, sino que la página host las muestra en un panel fijo al costado
   a través de la función onSeleccion que se pasa a iniciar(). */
window.CelabPen = (function () {
  const RADIUS = 4.5;         // mitad del lado del cuadrado del ancla (visual)
  const HIT_RADIUS = 10;      // radio real donde responde el click/arrastre
  const HANDLE_RADIUS = 4.5;  // manija de curva (visual)
  const HANDLE_HIT_RADIUS = 12;
  const ADD_THRESHOLD = 14;
  const CURVE_SAMPLES = 16;

  let svg, outline, outlineHalo, pointsGroup, handlesGroup;
  let onSeleccion = function () {};
  let points = [];
  let width = 400, height = 400;
  let dragIdx = null;
  let dragHandle = null;
  let dragMoved = false;
  let seleccionIdx = null;
  let puntosVisibles = true;

  const NS = "http://www.w3.org/2000/svg";

  function toLocal(e) {
    const rect = svg.getBoundingClientRect();
    const escalaX = width / rect.width;
    const escalaY = height / rect.height;
    return [(e.clientX - rect.left) * escalaX, (e.clientY - rect.top) * escalaY];
  }

  function bezierPoint(p1, p2, t) {
    const c1x = p1.x + p1.hx, c1y = p1.y + p1.hy;
    const c2x = p2.x - p2.hx, c2y = p2.y - p2.hy;
    const mt = 1 - t;
    const x = mt * mt * mt * p1.x + 3 * mt * mt * t * c1x + 3 * mt * t * t * c2x + t * t * t * p2.x;
    const y = mt * mt * mt * p1.y + 3 * mt * mt * t * c1y + 3 * mt * t * t * c2y + t * t * t * p2.y;
    return [x, y];
  }

  function pathD() {
    const n = points.length;
    if (n < 2) return "";
    let d = "M " + points[0].x + " " + points[0].y + " ";
    for (let i = 0; i < n; i++) {
      const p1 = points[i], p2 = points[(i + 1) % n];
      const c1x = p1.x + p1.hx, c1y = p1.y + p1.hy;
      const c2x = p2.x - p2.hx, c2y = p2.y - p2.hy;
      d += "C " + c1x + " " + c1y + ", " + c2x + " " + c2y + ", " + p2.x + " " + p2.y + " ";
    }
    d += "Z";
    return d;
  }

  function closestOnSegment(px, py, p1, p2) {
    let best = null;
    for (let s = 0; s <= CURVE_SAMPLES; s++) {
      const t = s / CURVE_SAMPLES;
      const [x, y] = bezierPoint(p1, p2, t);
      const dx = px - x, dy = py - y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (best === null || dist < best.dist) best = { dist, x, y };
    }
    return best;
  }

  function defaultHandleLen(idx) {
    const n = points.length;
    const prev = points[(idx - 1 + n) % n];
    const next = points[(idx + 1) % n];
    const p = points[idx];
    const dPrev = Math.hypot(p.x - prev.x, p.y - prev.y);
    const dNext = Math.hypot(next.x - p.x, next.y - p.y);
    let dx = next.x - prev.x, dy = next.y - prev.y;
    const len = Math.hypot(dx, dy) || 1;
    const scale = Math.min(dPrev, dNext) * 0.35;
    return [(dx / len) * scale, (dy / len) * scale];
  }

  function notificarSeleccion() {
    if (seleccionIdx === null || seleccionIdx >= points.length) {
      onSeleccion(null);
    } else {
      onSeleccion({ idx: seleccionIdx, curved: !!points[seleccionIdx].curved, total: points.length });
    }
  }

  function redraw() {
    const d = pathD();
    outlineHalo.setAttribute("d", d);
    outline.setAttribute("d", d);
    while (pointsGroup.firstChild) pointsGroup.removeChild(pointsGroup.firstChild);
    while (handlesGroup.firstChild) handlesGroup.removeChild(handlesGroup.firstChild);

    if (!puntosVisibles) return;

    if (seleccionIdx !== null && seleccionIdx < points.length && points[seleccionIdx].curved) {
      const p = points[seleccionIdx];
      const outX = p.x + p.hx, outY = p.y + p.hy;
      const inX = p.x - p.hx, inY = p.y - p.hy;
      const line = document.createElementNS(NS, "line");
      line.setAttribute("class", "handle-line");
      line.setAttribute("x1", inX); line.setAttribute("y1", inY);
      line.setAttribute("x2", outX); line.setAttribute("y2", outY);
      handlesGroup.appendChild(line);
      [["out", outX, outY], ["in", inX, inY]].forEach(([side, hx, hy]) => {
        const hit = document.createElementNS(NS, "circle");
        hit.setAttribute("cx", hx); hit.setAttribute("cy", hy);
        hit.setAttribute("r", HANDLE_HIT_RADIUS);
        hit.setAttribute("fill", "transparent");
        hit.setAttribute("pointer-events", "all");
        hit.setAttribute("class", "hit-target");
        hit.dataset.idx = seleccionIdx;
        hit.dataset.side = side;
        hit.addEventListener("pointerdown", onHandleDown);
        handlesGroup.appendChild(hit);

        const h = document.createElementNS(NS, "circle");
        h.setAttribute("cx", hx); h.setAttribute("cy", hy);
        h.setAttribute("r", HANDLE_RADIUS);
        h.setAttribute("fill", "#3a86ff");
        h.setAttribute("stroke", "#ffffff");
        h.setAttribute("stroke-width", "1");
        h.setAttribute("pointer-events", "none");
        handlesGroup.appendChild(h);
      });
    }

    points.forEach((p, i) => {
      if (i === seleccionIdx) {
        const ring = document.createElementNS(NS, "circle");
        ring.setAttribute("cx", p.x);
        ring.setAttribute("cy", p.y);
        ring.setAttribute("r", RADIUS + 4);
        ring.setAttribute("fill", "none");
        ring.setAttribute("stroke", "#ffffff");
        ring.setAttribute("stroke-width", "1.5");
        ring.setAttribute("stroke-dasharray", "2.5 2");
        ring.setAttribute("pointer-events", "none");
        pointsGroup.appendChild(ring);
      }

      const hit = document.createElementNS(NS, "circle");
      hit.setAttribute("cx", p.x);
      hit.setAttribute("cy", p.y);
      hit.setAttribute("r", HIT_RADIUS);
      hit.setAttribute("fill", "transparent");
      hit.setAttribute("pointer-events", "all");
      hit.setAttribute("class", "hit-target");
      hit.dataset.idx = i;
      hit.addEventListener("pointerdown", onPointDown);
      pointsGroup.appendChild(hit);

      // Ancla cuadrada (como Photoshop), sin capturar eventos propios: el
      // círculo invisible de arriba ya cubre un área más cómoda de agarrar.
      const sq = document.createElementNS(NS, "rect");
      sq.setAttribute("x", p.x - RADIUS);
      sq.setAttribute("y", p.y - RADIUS);
      sq.setAttribute("width", RADIUS * 2);
      sq.setAttribute("height", RADIUS * 2);
      sq.setAttribute("rx", 1);
      sq.setAttribute("fill", p.curved ? "#3a86ff" : "#00c853");
      sq.setAttribute("stroke", "#ffffff");
      sq.setAttribute("stroke-width", "1");
      sq.setAttribute("pointer-events", "none");
      pointsGroup.appendChild(sq);
    });
  }

  function onPointDown(e) {
    e.stopPropagation();
    dragIdx = parseInt(e.target.dataset.idx, 10);
    dragMoved = false;
    // Capturar en el <svg> (fijo) y no en el círculo invisible del punto:
    // ese círculo se destruye y se vuelve a crear en cada redraw() mientras
    // se arrastra, y si quedaba capturado él el arrastre se trababa (no
    // llegaba más el pointerup y el punto quedaba pegado al mouse).
    svg.setPointerCapture(e.pointerId);
  }
  function onHandleDown(e) {
    e.stopPropagation();
    dragHandle = { idx: parseInt(e.target.dataset.idx, 10), side: e.target.dataset.side };
    svg.setPointerCapture(e.pointerId);
  }

  function onPointerMove(e) {
    const [x, y] = toLocal(e);
    if (dragIdx !== null) {
      const p = points[dragIdx];
      p.x = Math.max(0, Math.min(width, x));
      p.y = Math.max(0, Math.min(height, y));
      dragMoved = true;
      redraw();
    } else if (dragHandle !== null) {
      const p = points[dragHandle.idx];
      if (dragHandle.side === "out") { p.hx = x - p.x; p.hy = y - p.y; }
      else { p.hx = p.x - x; p.hy = p.y - y; }
      redraw();
    }
  }
  function onPointerUp() {
    if (dragIdx !== null) {
      if (!dragMoved) {
        seleccionIdx = dragIdx;
        notificarSeleccion();
        redraw();
      }
      dragIdx = null;
    } else if (dragHandle !== null) {
      dragHandle = null;
    }
  }
  function onClick(e) {
    if (e.target.classList && e.target.classList.contains("hit-target")) return;
    if (seleccionIdx !== null) {
      seleccionIdx = null;
      notificarSeleccion();
      redraw();
      return;
    }
    if (!puntosVisibles) return;
    const [x, y] = toLocal(e);
    let best = null;
    const n = points.length;
    for (let i = 0; i < n; i++) {
      const r = closestOnSegment(x, y, points[i], points[(i + 1) % n]);
      if (best === null || r.dist < best.dist) best = Object.assign({ idx: i }, r);
    }
    if (best && best.dist <= ADD_THRESHOLD) {
      points.splice(best.idx + 1, 0, { x: best.x, y: best.y, curved: false, hx: 0, hy: 0 });
      redraw();
    }
  }

  function iniciar(cfg) {
    svg = document.getElementById(cfg.svgId);
    outline = document.getElementById(cfg.outlineId);
    outlineHalo = document.getElementById(cfg.outlineHaloId);
    pointsGroup = document.getElementById(cfg.pointsId);
    handlesGroup = document.getElementById(cfg.handlesId);
    onSeleccion = cfg.onSeleccion || function () {};
    width = cfg.width;
    height = cfg.height;
    points = (cfg.points || []).map((p) => ({ x: p.x, y: p.y, curved: !!p.curved, hx: p.hx || 0, hy: p.hy || 0 }));

    svg.addEventListener("pointermove", onPointerMove);
    svg.addEventListener("pointerup", onPointerUp);
    svg.addEventListener("click", onClick);
    redraw();
  }

  function eliminarSeleccionado() {
    if (seleccionIdx === null || points.length <= 3) return;
    points.splice(seleccionIdx, 1);
    seleccionIdx = null;
    notificarSeleccion();
    redraw();
  }

  function alternarCurva() {
    if (seleccionIdx === null) return;
    const p = points[seleccionIdx];
    p.curved = !p.curved;
    if (p.curved) { const [hx, hy] = defaultHandleLen(seleccionIdx); p.hx = hx; p.hy = hy; }
    else { p.hx = 0; p.hy = 0; }
    notificarSeleccion();
    redraw();
  }

  function alternarVisibilidadPuntos() {
    puntosVisibles = !puntosVisibles;
    if (!puntosVisibles) { seleccionIdx = null; notificarSeleccion(); }
    redraw();
    return puntosVisibles;
  }

  function puntosActuales() { return points; }

  return { iniciar, puntosActuales, eliminarSeleccionado, alternarCurva, alternarVisibilidadPuntos };
})();
