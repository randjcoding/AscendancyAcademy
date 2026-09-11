(function () {
  const desk = document.querySelector("[data-docs-desk]");
  if (!desk) return;

  const list = document.querySelector("[data-docs-list]");
  const filter = document.querySelector("[data-docs-filter]");
  const empty = document.querySelector("[data-docs-empty]");
  const panel = document.querySelector("[data-docs-preview]");
  const body = document.querySelector("[data-docs-body]");
  const titleEl = document.querySelector("[data-docs-title]");
  const metaEl = document.querySelector("[data-docs-meta]");
  const downloadEl = document.querySelector("[data-docs-download]");
  const biggerBtn = document.querySelector("[data-docs-bigger]");
  const closeBtn = document.querySelector("[data-docs-close]");
  const modal = document.querySelector("[data-docs-modal]");
  const modalBody = document.querySelector("[data-docs-modal-body]");
  const modalTitle = document.querySelector("[data-docs-modal-title]");
  const modalDownload = document.querySelector("[data-docs-modal-download]");
  const modalClose = document.querySelector("[data-docs-modal-close]");

  let current = null;
  let xlsxReady = null;
  let docxReady = null;

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      const found = Array.from(document.scripts).some(function (s) { return s.src === src; });
      if (found) return resolve();
      const el = document.createElement("script");
      el.src = src;
      el.onload = resolve;
      el.onerror = reject;
      document.body.appendChild(el);
    });
  }

  function ensureXlsx() {
    if (!xlsxReady) {
      xlsxReady = loadScript("https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js");
    }
    return xlsxReady;
  }

  function ensureDocx() {
    if (!docxReady) {
      docxReady = loadScript("https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js")
        .then(function () {
          return loadScript("https://cdn.jsdelivr.net/npm/docx-preview@0.3.5/dist/docx-preview.min.js");
        });
    }
    return docxReady;
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function fallback(download) {
    return '<div class="docs-fallback"><p>This file type needs to be downloaded to open.</p>' +
      '<a class="btn btn--primary" href="' + escapeHtml(download) + '">Download</a></div>';
  }

  function renderInto(target, file) {
    target.innerHTML = '<p class="muted">Opening…</p>';
    const kind = file.kind;
    const inline = file.inline;
    const download = file.download;
    if (kind === "pdf") {
      target.innerHTML = '<embed class="docs-embed" type="application/pdf" src="' + escapeHtml(inline) + '#toolbar=1">';
      return;
    }
    if (kind === "image") {
      target.innerHTML = '<div class="docs-image"><img src="' + escapeHtml(inline) + '" alt="' + escapeHtml(file.name) + '"></div>';
      return;
    }
    if (kind === "html") {
      target.innerHTML = '<iframe class="docs-embed" sandbox="allow-same-origin" src="' + escapeHtml(inline) + '" title="' + escapeHtml(file.name) + '"></iframe>';
      return;
    }
    if (kind === "text") {
      fetch(inline, { credentials: "same-origin" })
        .then(function (res) { return res.text(); })
        .then(function (text) {
          target.innerHTML = '<pre class="docs-text">' + escapeHtml(text) + "</pre>";
        })
        .catch(function () { target.innerHTML = fallback(download); });
      return;
    }
    if (kind === "docx") {
      ensureDocx()
        .then(function () { return fetch(inline, { credentials: "same-origin" }); })
        .then(function (res) { if (!res.ok) throw new Error("Could not open"); return res.blob(); })
        .then(function (blob) {
          target.innerHTML = "";
          return window.docx.renderAsync(blob, target, null, { inWrapper: true, breakPages: true });
        })
        .catch(function () { target.innerHTML = fallback(download); });
      return;
    }
    if (kind === "xlsx") {
      ensureXlsx()
        .then(function () { return fetch(inline, { credentials: "same-origin" }); })
        .then(function (res) { if (!res.ok) throw new Error("Could not open"); return res.arrayBuffer(); })
        .then(function (buf) {
          const wb = window.XLSX.read(buf, { type: "array" });
          const sheet = wb.SheetNames[0];
          const html = window.XLSX.utils.sheet_to_html(wb.Sheets[sheet]);
          let note = "";
          if (wb.SheetNames.length > 1) {
            note = '<p class="muted">Showing sheet “' + escapeHtml(sheet) + '”. Download for the rest.</p>';
          }
          target.innerHTML = note + '<div class="docs-sheet">' + html + "</div>";
        })
        .catch(function () { target.innerHTML = fallback(download); });
      return;
    }
    target.innerHTML = fallback(download);
  }

  function showPanel(file) {
    current = file;
    if (titleEl) titleEl.textContent = file.name;
    if (metaEl) metaEl.textContent = file.meta || "";
    if (downloadEl) downloadEl.href = file.download;
    panel.hidden = false;
    if (closeBtn) closeBtn.hidden = false;
    renderInto(body, file);
  }

  function openModal(file) {
    current = file || current;
    if (!current || !modal) return;
    if (modalTitle) modalTitle.textContent = current.name;
    if (modalDownload) modalDownload.href = current.download;
    modal.hidden = false;
    document.body.classList.add("docs-modal-open");
    renderInto(modalBody, current);
  }

  function closeModal() {
    if (!modal) return;
    modal.hidden = true;
    document.body.classList.remove("docs-modal-open");
    if (modalBody) modalBody.innerHTML = "";
  }

  function fileFromButton(btn) {
    return {
      kind: btn.getAttribute("data-kind"),
      name: btn.getAttribute("data-name"),
      meta: btn.getAttribute("data-meta"),
      inline: btn.getAttribute("data-inline"),
      download: btn.getAttribute("data-download"),
    };
  }

  if (filter) {
    filter.addEventListener("input", function () {
      const q = filter.value.trim().toLowerCase();
      let shown = 0;
      document.querySelectorAll("[data-docs-filterable]").forEach(function (row) {
        const hay = (row.getAttribute("data-filter") || "").toLowerCase();
        const match = !q || hay.indexOf(q) !== -1;
        row.hidden = !match;
        if (match) shown += 1;
      });
      if (empty) empty.hidden = shown !== 0;
    });
  }

  document.querySelectorAll("[data-docs-open]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const file = fileFromButton(btn);
      if (window.matchMedia("(max-width: 800px)").matches) {
        openModal(file);
      } else {
        showPanel(file);
      }
    });
  });

  if (biggerBtn) biggerBtn.addEventListener("click", function () { openModal(current); });
  if (closeBtn) closeBtn.addEventListener("click", function () {
    panel.hidden = true;
    closeBtn.hidden = true;
    if (body) body.innerHTML = "";
  });
  if (modalClose) modalClose.addEventListener("click", closeModal);
  if (modal) modal.addEventListener("click", function (event) {
    if (event.target === modal) closeModal();
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeModal();
  });

  if (desk.dataset.openKind) {
    const file = {
      kind: desk.dataset.openKind,
      name: desk.dataset.openName,
      meta: "",
      inline: desk.dataset.openInline,
      download: desk.dataset.openDownload,
    };
    if (window.matchMedia("(max-width: 800px)").matches) {
      openModal(file);
    } else {
      showPanel(file);
    }
  }
})();
