// CareConnect front-end helpers. Server-side validation is the real security
// control; this file only improves the user experience.
(function () {
  "use strict";

  // Mobile navigation
  var toggle = document.getElementById("nav-toggle");
  var links = document.getElementById("nav-links");
  if (toggle && links) {
    toggle.addEventListener("click", function () {
      var open = links.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  var form = document.getElementById("booking-form");
  if (!form) { return; }

  var doctor = document.getElementById("doctor_id");
  var timeSel = document.getElementById("appointment_time");
  var dateInput = document.getElementById("appointment_date");

  var DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  function allowedDays(spec) {
    var set = {};
    spec.split(",").forEach(function (part) {
      part = part.trim();
      if (part.indexOf("-") > -1) {
        var bounds = part.split("-");
        var i = DAYS.indexOf(bounds[0].trim()), j = DAYS.indexOf(bounds[1].trim());
        for (var k = i; k !== (j + 1) % 7; k = (k + 1) % 7) { set[k] = true; }
      } else { set[DAYS.indexOf(part)] = true; }
    });
    return set;
  }

  // Show only the time slots the selected doctor offers.
  function filterTimes() {
    var opt = doctor.options[doctor.selectedIndex];
    var start = opt && opt.dataset.start, end = opt && opt.dataset.end;
    Array.prototype.forEach.call(timeSel.options, function (o) {
      if (!o.value) { return; }
      var visible = !start || (o.value >= start && o.value < end);
      o.hidden = !visible;
      o.disabled = !visible;
    });
    if (timeSel.selectedOptions[0] && timeSel.selectedOptions[0].disabled) { timeSel.value = ""; }
  }
  doctor.addEventListener("change", filterTimes);
  filterTimes();

  function setError(name, message) {
    var el = form.querySelector('[data-error-for="' + name + '"]');
    if (!el) { return; }
    el.textContent = message;
    el.parentElement.classList.toggle("has-error", !!message);
  }

  form.addEventListener("submit", function (event) {
    var ok = true;
    var name = form.patient_name.value.trim();
    var email = form.email.value.trim();

    setError("patient_name", /^[A-Za-z][A-Za-z .'-]{1,79}$/.test(name) ? "" : "Use 2-80 letters; spaces, . ' and - are allowed.");
    setError("email", /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) ? "" : "Enter a valid email address (use a fictional one).");
    setError("doctor_id", doctor.value ? "" : "Please choose a doctor from the list.");
    setError("appointment_time", timeSel.value ? "" : "Please choose a time.");
    setError("reason", form.reason.value.length > 200 ? "Please keep the reason under 200 characters." : "");

    var dateMsg = "";
    if (!dateInput.value) { dateMsg = "Please choose a date."; }
    else if (dateInput.value < form.dataset.minDate || dateInput.value > form.dataset.maxDate) { dateMsg = "Choose a date within the booking window."; }
    else if (doctor.value) {
      var d = new Date(dateInput.value + "T00:00:00");
      var weekday = (d.getDay() + 6) % 7; // Monday = 0
      if (!allowedDays(doctor.options[doctor.selectedIndex].dataset.days)[weekday]) { dateMsg = "The selected doctor does not work on that day."; }
    }
    setError("appointment_date", dateMsg);

    form.querySelectorAll(".error-text").forEach(function (el) { if (el.textContent) { ok = false; } });
    if (!ok) {
      event.preventDefault();
      var first = form.querySelector(".has-error input, .has-error select");
      if (first) { first.focus(); }
    }
  });
})();
