(function () {
  const course = document.getElementById("quickCourse");
  const book = document.getElementById("quickBook");
  if (!course || !book) return;

  function filterBooks() {
    const id = course.value;
    let firstVisible = null;
    Array.from(book.options).forEach(function (opt) {
      if (!opt.value || opt.value === "0") {
        opt.hidden = false;
        return;
      }
      const match = opt.getAttribute("data-course") === id;
      opt.hidden = !match;
      if (match && !firstVisible) firstVisible = opt;
    });
    const selected = book.options[book.selectedIndex];
    if (selected && selected.hidden) {
      book.value = firstVisible ? firstVisible.value : "0";
    }
  }

  course.addEventListener("change", filterBooks);
  filterBooks();

  const read = document.querySelector("[data-read-pages]");
  if (!read) return;
  const files = read.querySelector("[data-read-files]");
  const provider = read.querySelector("[data-read-provider]");
  const keySel = read.querySelector("[data-read-key]");
  const estimate = read.querySelector("[data-read-estimate]");
  const balance = read.querySelector("[data-read-balance]");
  const status = read.querySelector("[data-read-status]");
  const run = read.querySelector("[data-read-run]");
  const pages = document.getElementById("quickPages");
  const score = document.getElementById("quickScore");
  const work = document.querySelector('#quickAssign input[name="has_work"]');

  function imageCount() {
    return files && files.files ? files.files.length : 0;
  }

  function refreshEstimate() {
    if (!provider || !provider.value) {
      if (estimate) estimate.textContent = "Pick a model and photos to see the cost.";
      return;
    }
    const n = Math.max(1, imageCount());
    fetch("/api/ai/estimate?provider=" + encodeURIComponent(provider.value) + "&images=" + n, { credentials: "same-origin" })
      .then(function (resp) { return resp.json(); })
      .then(function (data) {
        if (estimate) estimate.textContent = (data.label || "") + (data.model ? " · " + data.model : "");
      })
      .catch(function () {
        if (estimate) estimate.textContent = "Could not estimate right now.";
      });
  }

  function refreshBalance() {
    if (!balance) return;
    const keyId = keySel ? keySel.value : "0";
    if (provider && provider.value === "gemma") {
      balance.textContent = "Gemma is free when the Mac is on.";
      return;
    }
    fetch("/api/ai/balance?key_id=" + encodeURIComponent(keyId), { credentials: "same-origin" })
      .then(function (resp) { return resp.json(); })
      .then(function (data) {
        balance.textContent = data.label || "";
      })
      .catch(function () {
        balance.textContent = "";
      });
  }

  if (files) files.addEventListener("change", refreshEstimate);
  if (provider) provider.addEventListener("change", function () {
    if (keySel && provider.value) {
      Array.from(keySel.options).forEach(function (opt) {
        if (!opt.value || opt.value === "0") return;
        opt.hidden = opt.getAttribute("data-provider") !== provider.value;
      });
      const visible = Array.from(keySel.options).find(function (opt) {
        return opt.value && opt.value !== "0" && !opt.hidden;
      });
      if (visible) keySel.value = visible.value;
    }
    refreshEstimate();
    refreshBalance();
  });
  if (keySel) keySel.addEventListener("change", refreshBalance);

  if (run) {
    run.addEventListener("click", function () {
      if (!provider.value) {
        if (status) {
          status.hidden = false;
          status.textContent = "Pick a model first.";
        }
        return;
      }
      if (!imageCount()) {
        if (status) {
          status.hidden = false;
          status.textContent = "Add at least one photo.";
        }
        return;
      }
      const data = new FormData();
      data.append("provider", provider.value);
      data.append("key_id", keySel ? keySel.value : "0");
      data.append("book_id", book.value || "0");
      Array.from(files.files).forEach(function (file) { data.append("files", file); });
      if (status) {
        status.hidden = false;
        status.textContent = "Reading the pages…";
      }
      fetch("/teacher/read-pages", { method: "POST", body: data, credentials: "same-origin" })
        .then(function (resp) { return resp.json().then(function (body) { return { ok: resp.ok, body: body }; }); })
        .then(function (result) {
          const body = result.body || {};
          if (!result.ok) {
            if (status) status.textContent = body.error || "Could not read those photos. Type the pages.";
            return;
          }
          if (pages && body.pages) pages.value = body.pages;
          if (score && body.score != null) score.value = body.score;
          if (work) work.checked = body.has_work !== false;
          if (status) {
            status.textContent = body.pages
              ? "Check the pages and save if they look right."
              : "Could not see the page number. Type it, then save.";
          }
        })
        .catch(function () {
          if (status) status.textContent = "Lookup is busy. Type the pages.";
        });
    });
  }
})();
