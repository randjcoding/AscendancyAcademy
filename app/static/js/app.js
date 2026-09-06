(function () {
  const navToggle = document.getElementById("navToggle");
  const topbar = document.getElementById("topbar");
  if (navToggle && topbar) {
    navToggle.addEventListener("click", function () {
      const open = topbar.classList.toggle("is-nav-open");
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  const theme = document.documentElement.getAttribute("data-theme") || "academy";
  try { localStorage.setItem("aa.theme", theme); } catch (e) {}
})();
