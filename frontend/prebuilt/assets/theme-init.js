// Runs before the app paints, so a light-mode visitor never sees a dark flash.
(function () {
  var t = null;
  try { t = localStorage.getItem("hygiene-theme"); } catch (e) { /* storage blocked */ }
  if (t !== "dark" && t !== "light") t = matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", t);
})();
