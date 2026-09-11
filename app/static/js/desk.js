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
})();
