(function () {
  var btn = document.getElementById("theme-toggle");
  if (!btn) return;
  btn.addEventListener("click", function () {
    var root = document.documentElement;
    var actual = root.getAttribute("data-theme");
    var oscuroAhora = actual === "dark" || (!actual && window.matchMedia("(prefers-color-scheme: dark)").matches);
    var siguiente = oscuroAhora ? "light" : "dark";
    root.setAttribute("data-theme", siguiente);
    localStorage.setItem("celab-theme", siguiente);
  });
})();
