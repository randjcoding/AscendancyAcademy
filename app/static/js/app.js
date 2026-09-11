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
    return document.documentElement.getAttribute("data-theme") || "ascendancy";
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

  function useCode(root, raw) {
    const input = root.querySelector("[data-book-query]");
    if (input) input.value = raw;
    searchBooks(root);
  }

  function closeScan(overlay, stream) {
    if (stream) stream.getTracks().forEach(function (track) { track.stop(); });
    if (overlay) overlay.remove();
  }

  function readBarcodeFromFile(root, file, photo) {
    const box = root.querySelector("[data-book-hits]");
    if (!file) return;
    if (!window.BarcodeDetector) {
      if (box) {
        box.hidden = false;
        box.textContent = "This browser cannot read barcodes. Type the number under the bars.";
      }
      return;
    }
    if (box) {
      box.hidden = false;
      box.textContent = "Reading the barcode…";
    }
    const detector = new BarcodeDetector({ formats: ["ean_13", "ean_8", "upc_a", "upc_e"] });
    createImageBitmap(file)
      .then(function (bitmap) { return detector.detect(bitmap); })
      .then(function (codes) {
        const raw = codes.length ? (codes[0].rawValue || "") : "";
        if (raw) {
          useCode(root, raw);
        } else if (box) {
          box.textContent = "Could not read that photo. Type the number under the bars.";
        }
      })
      .catch(function () {
        if (box) {
          box.hidden = false;
          box.textContent = "Could not read that photo. Type the number under the bars.";
        }
      })
      .finally(function () {
        if (photo) photo.value = "";
      });
  }

  function startScan(root) {
    const box = root.querySelector("[data-book-hits]");
    const photo = root.querySelector("[data-book-photo]");
    const canCamera = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.BarcodeDetector);
    if (!canCamera) {
      if (photo) {
        photo.click();
        if (box) {
          box.hidden = false;
          box.textContent = "Pick a photo of the barcode, or type the number.";
        }
        return;
      }
      if (box) {
        box.hidden = false;
        box.textContent = "Scan needs a camera. Type the ISBN or UPC instead.";
      }
      return;
    }

    const overlay = document.createElement("div");
    overlay.className = "book-scan";
    overlay.innerHTML =
      "<div><p class=\"book-scan__hint\">Point the camera at the barcode</p>" +
      "<video playsinline autoplay></video>" +
      "<div class=\"book-scan__actions\">" +
      "<button type=\"button\" class=\"btn\" data-scan-photo>Use a photo</button> " +
      "<button type=\"button\" class=\"btn\" data-scan-cancel>Cancel</button>" +
      "</div></div>";
    document.body.appendChild(overlay);
    const video = overlay.querySelector("video");
    let stream = null;
    let timer = null;

    function stop() {
      if (timer) clearInterval(timer);
      closeScan(overlay, stream);
    }

    overlay.querySelector("[data-scan-cancel]").addEventListener("click", stop);
    overlay.querySelector("[data-scan-photo]").addEventListener("click", function () {
      stop();
      if (photo) photo.click();
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
            stop();
            useCode(root, raw);
          }).catch(function () {});
        }, 400);
      })
      .catch(function () {
        stop();
        if (photo) photo.click();
        if (box) {
          box.hidden = false;
          box.textContent = "Camera was blocked. Use a photo or type the number.";
        }
      });
  }

  document.querySelectorAll("[data-book-find]").forEach(function (root) {
    const searchBtn = root.querySelector("[data-book-search]");
    const scanBtn = root.querySelector("[data-book-scan]");
    const photo = root.querySelector("[data-book-photo]");
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
    if (scanBtn) scanBtn.addEventListener("click", function () { startScan(root); });
    if (photo) {
      photo.addEventListener("change", function () {
        if (photo.files && photo.files[0]) readBarcodeFromFile(root, photo.files[0], photo);
      });
    }
  });
})();
