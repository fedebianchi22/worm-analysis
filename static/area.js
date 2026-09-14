/* Selector de área rectangular tipo "marquee" (Photoshop). Se usa antes de
   dibujar un gusano nuevo desde cero: primero se enmarca en qué parte de la
   foto completa está, oscureciendo el resto, y recién después se pasa al
   editor de contorno (pen.js) ya recortado y con zoom sobre esa zona.

   Se inicializa con CelabArea.iniciar(...) y expone CelabArea.rectActual()
   para leer el recuadro final antes de enviarlo. */
window.CelabArea = (function () {
  const HANDLE = 7;       // mitad del lado del cuadrado de esquina (visual)
  const HANDLE_HIT = 14;  // radio real donde responde el click/arrastre
  const MIN_SIZE = 30;

  const NS = "http://www.w3.org/2000/svg";

  let svg, mascara, rectEl, handlesGroup;
  let width = 400, height = 400;
  let rect = { x0: 0, y0: 0, x1: 100, y1: 100 };
  let modo = null; // "mover" | "tl" | "tr" | "bl" | "br"
  let inicioPuntero = null;
  let rectInicio = null;

  function toLocal(e) {
    const r = svg.getBoundingClientRect();
    const escalaX = width / r.width;
    const escalaY = height / r.height;
    return [(e.clientX - r.left) * escalaX, (e.clientY - r.top) * escalaY];
  }

  function el(tag, attrs) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  function redraw() {
    const x0 = Math.min(rect.x0, rect.x1), x1 = Math.max(rect.x0, rect.x1);
    const y0 = Math.min(rect.y0, rect.y1), y1 = Math.max(rect.y0, rect.y1);

    rectEl.setAttribute("x", x0);
    rectEl.setAttribute("y", y0);
    rectEl.setAttribute("width", x1 - x0);
    rectEl.setAttribute("height", y1 - y0);

    mascara.innerHTML = "";
    const oscuro = "rgba(0,0,0,.55)";
    mascara.appendChild(el("rect", { x: 0, y: 0, width, height: y0, fill: oscuro }));
    mascara.appendChild(el("rect", { x: 0, y: y1, width, height: height - y1, fill: oscuro }));
    mascara.appendChild(el("rect", { x: 0, y: y0, width: x0, height: y1 - y0, fill: oscuro }));
    mascara.appendChild(el("rect", { x: x1, y: y0, width: width - x1, height: y1 - y0, fill: oscuro }));

    handlesGroup.innerHTML = "";
    const esquinas = [["tl", x0, y0], ["tr", x1, y0], ["bl", x0, y1], ["br", x1, y1]];
    for (const [nombre, cx, cy] of esquinas) {
      const h = el("rect", {
        x: cx - HANDLE, y: cy - HANDLE, width: HANDLE * 2, height: HANDLE * 2,
        fill: "#ffb020", stroke: "#1a1a2e", "stroke-width": 1.2, rx: 2,
        "data-esquina": nombre, style: "cursor:nwse-resize",
      });
      handlesGroup.appendChild(h);
    }
  }

  function onDown(e) {
    const [x, y] = toLocal(e);
    const esquina = e.target && e.target.getAttribute && e.target.getAttribute("data-esquina");
    if (esquina) {
      modo = esquina;
    } else {
      const x0 = Math.min(rect.x0, rect.x1), x1 = Math.max(rect.x0, rect.x1);
      const y0 = Math.min(rect.y0, rect.y1), y1 = Math.max(rect.y0, rect.y1);
      if (x < x0 || x > x1 || y < y0 || y > y1) return;
      modo = "mover";
    }
    inicioPuntero = [x, y];
    rectInicio = { ...rect };
    svg.setPointerCapture(e.pointerId);
    e.preventDefault();
  }

  function onMove(e) {
    if (!modo) return;
    const [x, y] = toLocal(e);
    const dx = x - inicioPuntero[0], dy = y - inicioPuntero[1];

    if (modo === "mover") {
      const w = rectInicio.x1 - rectInicio.x0, h = rectInicio.y1 - rectInicio.y0;
      let nx0 = rectInicio.x0 + dx, ny0 = rectInicio.y0 + dy;
      nx0 = clamp(nx0, 0, width - w);
      ny0 = clamp(ny0, 0, height - h);
      rect = { x0: nx0, y0: ny0, x1: nx0 + w, y1: ny0 + h };
    } else {
      rect = { ...rectInicio };
      if (modo === "tl") { rect.x0 = clamp(rectInicio.x0 + dx, 0, rect.x1 - MIN_SIZE); rect.y0 = clamp(rectInicio.y0 + dy, 0, rect.y1 - MIN_SIZE); }
      if (modo === "tr") { rect.x1 = clamp(rectInicio.x1 + dx, rect.x0 + MIN_SIZE, width); rect.y0 = clamp(rectInicio.y0 + dy, 0, rect.y1 - MIN_SIZE); }
      if (modo === "bl") { rect.x0 = clamp(rectInicio.x0 + dx, 0, rect.x1 - MIN_SIZE); rect.y1 = clamp(rectInicio.y1 + dy, rect.y0 + MIN_SIZE, height); }
      if (modo === "br") { rect.x1 = clamp(rectInicio.x1 + dx, rect.x0 + MIN_SIZE, width); rect.y1 = clamp(rectInicio.y1 + dy, rect.y0 + MIN_SIZE, height); }
    }
    redraw();
  }

  function onUp(e) {
    if (modo) svg.releasePointerCapture(e.pointerId);
    modo = null;
  }

  function iniciar(cfg) {
    svg = document.getElementById(cfg.svgId);
    mascara = document.getElementById(cfg.maskId);
    rectEl = document.getElementById(cfg.rectId);
    handlesGroup = document.getElementById(cfg.handlesId);
    width = cfg.width;
    height = cfg.height;
    rect = { ...cfg.rect };

    svg.addEventListener("pointerdown", onDown);
    svg.addEventListener("pointermove", onMove);
    svg.addEventListener("pointerup", onUp);
    svg.addEventListener("pointercancel", onUp);

    redraw();
  }

  function rectActual() {
    const x0 = Math.round(Math.min(rect.x0, rect.x1));
    const y0 = Math.round(Math.min(rect.y0, rect.y1));
    const x1 = Math.round(Math.max(rect.x0, rect.x1));
    const y1 = Math.round(Math.max(rect.y0, rect.y1));
    return { x0, y0, x1, y1 };
  }

  return { iniciar, rectActual };
})();
