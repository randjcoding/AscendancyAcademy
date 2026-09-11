(function () {
  const navToggle = document.getElementById("navToggle");
  const topbar = document.getElementById("topbar");
  if (navToggle && topbar) {
    navToggle.addEventListener("click", function () {
      const open = topbar.classList.toggle("is-nav-open");
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") || "academy";
  }

  function currentDensity() {
    return document.documentElement.getAttribute("data-density") || "cozy";
  }

  function applyLook(theme, density) {
    if (theme) document.documentElement.setAttribute("data-theme", theme);
    if (density) document.documentElement.setAttribute("data-density", density);
    try {
      localStorage.setItem("aa.theme", currentTheme());
      localStorage.setItem("aa.density", currentDensity());
    } catch (e) {}
    document.querySelectorAll(".look-swatch, .theme-pick").forEach(function (btn) {
      const value = btn.getAttribute("data-theme-preview");
      if (value) btn.classList.toggle("is-on", value === currentTheme());
    });
    document.querySelectorAll("[data-density-pick]").forEach(function (btn) {
      const on = btn.getAttribute("data-density-pick") === currentDensity();
      btn.classList.toggle("btn--primary", on);
    });
    document.querySelectorAll('form[action="/theme"] input[name="theme"]').forEach(function (input) {
      if (input.closest("form").querySelector('button[data-theme-preview]')) return;
      input.value = currentTheme();
    });
    document.querySelectorAll('form[action="/theme"] input[name="density"]').forEach(function (input) {
      if (input.closest("form").querySelector("[data-density-pick]")) return;
      input.value = currentDensity();
    });
  }

  applyLook(currentTheme(), currentDensity());

  document.querySelectorAll("form.look-form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      const data = new FormData(form);
      applyLook(String(data.get("theme") || ""), String(data.get("density") || ""));
      const menu = document.getElementById("lookMenu");
      if (menu) menu.removeAttribute("open");
      fetch("/theme", { method: "POST", body: data, credentials: "same-origin" }).catch(function () {
        form.submit();
      });
    });
  });

  const kindLabels = {
    workbook: "Workbook",
    curriculum: "Curriculum",
    novel: "Novel",
    textbook: "Textbook",
    other: "Other",
  };

  function fillBook(root, hit) {
    const set = function (name, value) {
      const el = root.querySelector("[data-book-" + name + "]");
      if (el) el.value = value || "";
    };
    set("title", hit.title);
    set("author", hit.author);
    set("isbn", hit.isbn);
    set("upc", hit.upc);
    set("kind", hit.kind);
  }

  function showHits(root, hits) {
    const box = root.querySelector("[data-book-hits]");
    if (!box) return;
    box.innerHTML = "";
    if (!hits.length) {
      box.hidden = false;
      box.textContent = "Nothing found. Type the title and save it anyway.";
      return;
    }
    hits.forEach(function (hit) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "book-hit";
      const meta = [kindLabels[hit.kind] || "Book", hit.author, hit.isbn || hit.upc]
        .filter(Boolean)
        .join(" · ");
      btn.innerHTML = "<strong></strong><span class=\"muted\"></span>";
      btn.querySelector("strong").textContent = hit.title;
      btn.querySelector("span").textContent = meta;
      btn.addEventListener("click", function () {
        fillBook(root, hit);
        box.hidden = true;
      });
      box.appendChild(btn);
    });
    box.hidden = false;
  }

  function searchBooks(root) {
    const query = (root.querySelector("[data-book-query]") || {}).value || "";
    const q = query.trim();
    const box = root.querySelector("[data-book-hits]");
    if (!q) {
      if (box) {
        box.hidden = false;
        box.textContent = "Type an ISBN, UPC, or title first.";
      }
      return;
    }
    if (box) {
      box.hidden = false;
      box.textContent = "Looking it up…";
    }
    fetch("/api/books/lookup?q=" + encodeURIComponent(q), { credentials: "same-origin" })
      .then(function (resp) { return resp.json(); })
      .then(function (data) {
        const hits = (data && data.results) || [];
        showHits(root, hits);
        if (hits.length === 1) fillBook(root, hits[0]);
      })
      .catch(function () {
        if (box) {
          box.hidden = false;
          box.textContent = "Lookup is busy. Type the title and save it.";
        }
      });
  }

  function closeScan(overlay, stream) {
    if (stream) stream.getTracks().forEach(function (track) { track.stop(); });
    if (overlay) overlay.remove();
  }

  function startScan(root) {
    if (!navigator.mediaDevices || !window.BarcodeDetector) return;
    const overlay = document.createElement("div");
    overlay.className = "book-scan";
    overlay.innerHTML = "<div><video playsinline autoplay></video><div class=\"book-scan__actions\"><button type=\"button\" class=\"btn\">Cancel</button></div></div>";
    document.body.appendChild(overlay);
    const video = overlay.querySelector("video");
    const cancel = overlay.querySelector("button");
    let stream = null;
    let timer = null;
    cancel.addEventListener("click", function () {
      if (timer) clearInterval(timer);
      closeScan(overlay, stream);
    });
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
      .then(function (media) {
        stream = media;
        video.srcObject = media;
        const detector = new BarcodeDetector({
          formats: ["ean_13", "ean_8", "upc_a", "upc_e"],
        });
        timer = setInterval(function () {
          detector.detect(video).then(function (codes) {
            if (!codes.length) return;
            const raw = codes[0].rawValue || "";
            if (!raw) return;
            clearInterval(timer);
            closeScan(overlay, stream);
            const input = root.querySelector("[data-book-query]");
            if (input) input.value = raw;
            searchBooks(root);
          }).catch(function () {});
        }, 400);
      })
      .catch(function () {
        closeScan(overlay, stream);
        const box = root.querySelector("[data-book-hits]");
        if (box) {
          box.hidden = false;
          box.textContent = "Camera is not available. Type the number instead.";
        }
      });
  }

  document.querySelectorAll("[data-book-find]").forEach(function (root) {
    const searchBtn = root.querySelector("[data-book-search]");
    const scanBtn = root.querySelector("[data-book-scan]");
    const query = root.querySelector("[data-book-query]");
    if (searchBtn) searchBtn.addEventListener("click", function () { searchBooks(root); });
    if (query) {
      query.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
          event.preventDefault();
          searchBooks(root);
        }
      });
    }
    if (scanBtn && window.BarcodeDetector && navigator.mediaDevices) {
      scanBtn.hidden = false;
      scanBtn.addEventListener("click", function () { startScan(root); });
    }
  });
})();
