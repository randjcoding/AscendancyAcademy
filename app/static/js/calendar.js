(function () {
  const el = document.getElementById("aa-calendar");
  if (!el || !window.FullCalendar) return;
  const calendar = new FullCalendar.Calendar(el, {
    initialView: window.matchMedia("(max-width: 800px)").matches ? "listMonth" : "dayGridMonth",
    height: "auto",
    timeZone: "America/New_York",
    headerToolbar: {
      left: "prev,next today",
      center: "title",
      right: "dayGridMonth,timeGridWeek,listMonth",
    },
    events: "/api/calendar/events",
    eventClick: function (info) {
      const href = info.event.extendedProps && info.event.extendedProps.href;
      if (href) window.location.href = href;
    },
  });
  calendar.render();
})();
