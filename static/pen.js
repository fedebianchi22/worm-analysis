/* Editor de contorno tipo "pluma" (Photoshop). Dibuja sobre un <svg>, sin
   dependencias externas. Se inicializa con CelabPen.iniciar(...) y expone
   CelabPen.puntosActuales() para leer el resultado antes de enviarlo. */
window.CelabPen = (function () {
  const RADIUS = 7;
  const HANDLE_RADIUS = 5;
  const ADD_THRESHOLD = 16;
  const CURVE_SAMPLES = 16;

  let svg, outline, pointsGroup, handlesGroup, menu, btnDel, btnCurve;
  let points = [];
  let width = 400, height = 400;
  let dragIdx = null;
  let dragHandle = null;
  let dragMoved = false;
  let menuIdx = null;

  function toLocal(e) {
    const rect = svg.getBoundingClientRect();
    return [e.clientX - rect.left, e.clientY - rect.top];
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

  function redraw() {
    outline.setAttribute("d", pathD());
    while (pointsGroup.firstChild) pointsGroup.removeChild(pointsGroup.firstChild);
    while (handlesGroup.firstChild) handlesGroup.removeChild(handlesGroup.firstChild);

    if (menuIdx !== null && menuIdx < points.length && points[menuIdx].curved) {
      const p = points[menuIdx];
      const outX = p.x + p.hx, outY = p.y + p.hy;
      const inX = p.x - p.hx, inY = p.y - p.hy;
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("class", "handle-line");
      line.setAttribute("x1", inX); line.setAttribute("y1", inY);
      line.setAttribute("x2", outX); line.setAttribute("y2", outY);
      handlesGroup.appendChild(line);
      [["out", outX, outY], ["in", inX, inY]].forEach(([side, hx, hy]) => {
        const h = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        h.setAttribute("class", "handle");
        h.setAttribute("cx", hx); h.setAttribute("cy", hy);
        h.setAttribute("r", HANDLE_RADIUS);
        h.setAttribute("fill", "#3a86ff");
        h.setAttribute("stroke", "#ffffff");
        h.setAttribute("stroke-width", "1.2");
        h.dataset.idx = menuIdx;
        h.dataset.side = side;
        h.addEventListener("pointerdown", onHandleDown);
        handlesGroup.appendChild(h);
      });
    }

    points.forEach((p, i) => {
      const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      c.setAttribute("class", "pt");
      c.setAttribute("cx", p.x);
      c.setAttribute("cy", p.y);
      c.setAttribute("r", RADIUS);
      c.setAttribute("fill", p.curved ? "#3a86ff" : "#00c853");
      c.setAttribute("stroke", "#ffffff");
      c.setAttribute("stroke-width", "1.5");
      c.dataset.idx = i;
      c.addEventListener("pointerdown", onPointDown);
      pointsGroup.appendChild(c);
    });

    if (menuIdx !== null && menuIdx < points.length) positionMenu(menuIdx);
    else hideMenu();
  }

  function positionMenu(idx) {
    const p = points[idx];
    menu.style.left = p.x + "px";
    menu.style.top = (p.y - RADIUS - 8) + "px";
    menu.style.display = "flex";
    btnCurve.classList.toggle("active", !!p.curved);
    btnCurve.textContent = p.curved ? "Hacer recto" : "Curvar este punto";
    const disable = points.length <= 3;
    btnDel.disabled = disable;
  }
  function hideMenu() { menuIdx = null; menu.style.display = "none"; }

  function onPointDown(e) {
    e.stopPropagation();
    dragIdx = parseInt(e.target.dataset.idx, 10);
    dragMoved = false;
    e.target.setPointerCapture(e.pointerId);
  }
  function onHandleDown(e) {
    e.stopPropagation();
    dragHandle = { idx: parseInt(e.target.dataset.idx, 10), side: e.target.dataset.side };
    e.target.setPointerCapture(e.pointerId);
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
      if (!dragMoved) { menuIdx = dragIdx; redraw(); }
      dragIdx = null;
    } else if (dragHandle !== null) {
      dragHandle = null;
    }
  }
  function onClick(e) {
    if (e.target.classList && (e.target.classList.contains("pt") || e.target.classList.contains("handle"))) return;
    if (menuIdx !== null) { hideMenu(); redraw(); return; }
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
    pointsGroup = document.getElementById(cfg.pointsId);
    handlesGroup = document.getElementById(cfg.handlesId);
    menu = document.getElementById(cfg.menuId);
    btnDel = document.getElementById(cfg.btnDelId);
    btnCurve = document.getElementById(cfg.btnCurveId);
    width = cfg.width;
    height = cfg.height;
    points = (cfg.points || []).map((p) => ({ x: p.x, y: p.y, curved: !!p.curved, hx: p.hx || 0, hy: p.hy || 0 }));

    svg.addEventListener("pointermove", onPointerMove);
    svg.addEventListener("pointerup", onPointerUp);
    svg.addEventListener("click", onClick);
    btnDel.addEventListener("click", () => {
      if (menuIdx === null || points.length <= 3) return;
      points.splice(menuIdx, 1);
      hideMenu();
      redraw();
    });
    btnCurve.addEventListener("click", () => {
      if (menuIdx === null) return;
      const p = points[menuIdx];
      p.curved = !p.curved;
      if (p.curved) { const [hx, hy] = defaultHandleLen(menuIdx); p.hx = hx; p.hy = hy; }
      else { p.hx = 0; p.hy = 0; }
      redraw();
    });
    document.getElementById(cfg.wrapId).addEventListener("pointerdown", (e) => {
      if (e.target === svg || e.target.id === cfg.bgId) {
        if (menuIdx !== null) { hideMenu(); redraw(); }
      }
    });
    redraw();
  }

  function puntosActuales() { return points; }

  return { iniciar, puntosActuales };
})();
