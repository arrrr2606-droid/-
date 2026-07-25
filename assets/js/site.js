/* Альфа Машинери — интерфейс сайта. Без зависимостей. */
(function () {
  "use strict";

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  };

  /* --- Навигация: бургер и мега-меню ------------------------ */

  function initNav() {
    var burger = $(".burger");
    var nav = $(".nav");
    if (burger && nav) {
      burger.addEventListener("click", function () {
        var open = nav.classList.toggle("is-open");
        burger.setAttribute("aria-expanded", String(open));
      });
    }

    var toggles = $$("[data-megamenu]");
    toggles.forEach(function (btn) {
      var menu = document.getElementById(btn.getAttribute("aria-controls"));
      if (!menu) return;
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        var open = !menu.classList.contains("is-open");
        closeMenus();
        if (open) {
          menu.classList.add("is-open");
          btn.setAttribute("aria-expanded", "true");
        }
      });
    });

    function closeMenus() {
      toggles.forEach(function (btn) {
        var menu = document.getElementById(btn.getAttribute("aria-controls"));
        if (menu) menu.classList.remove("is-open");
        btn.setAttribute("aria-expanded", "false");
      });
    }

    document.addEventListener("click", function (e) {
      if (!e.target.closest(".header")) closeMenus();
    });

    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      closeMenus();
      if (nav && nav.classList.contains("is-open")) {
        nav.classList.remove("is-open");
        if (burger) burger.setAttribute("aria-expanded", "false");
      }
    });
  }

  /* --- Табы -------------------------------------------------- */

  function initTabs() {
    $$("[data-tabs]").forEach(function (root) {
      var btns = $$("[role=tab]", root);
      if (!btns.length) return;

      function select(target) {
        btns.forEach(function (btn) {
          var on = btn === target;
          btn.setAttribute("aria-selected", String(on));
          btn.tabIndex = on ? 0 : -1;
          var panel = document.getElementById(btn.getAttribute("aria-controls"));
          if (panel) panel.hidden = !on;
        });
      }

      btns.forEach(function (btn, i) {
        btn.addEventListener("click", function () { select(btn); });
        btn.addEventListener("keydown", function (e) {
          var step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
          if (!step) return;
          e.preventDefault();
          var next = btns[(i + step + btns.length) % btns.length];
          next.focus();
          select(next);
        });
      });

      select(btns.filter(function (b) {
        return b.getAttribute("aria-selected") === "true";
      })[0] || btns[0]);
    });
  }

  /* --- Аккордеон --------------------------------------------- */

  function initAccordion() {
    $$(".accordion__btn").forEach(function (btn) {
      var panel = document.getElementById(btn.getAttribute("aria-controls"));
      if (!panel) return;
      btn.addEventListener("click", function () {
        var open = btn.getAttribute("aria-expanded") === "true";
        btn.setAttribute("aria-expanded", String(!open));
        panel.hidden = open;
      });
    });
  }

  /* --- Галерея и лайтбокс ------------------------------------ */

  function initGallery() {
    var gallery = $("[data-gallery]");
    if (!gallery) return;

    var main = $(".gallery__main img", gallery);
    var thumbs = $$(".gallery__thumb", gallery);
    var stage = $(".gallery__main", gallery);
    var sources = thumbs.map(function (t) {
      return { src: t.dataset.full, alt: t.dataset.alt || "", cutout: t.dataset.cutout === "true" };
    });
    if (!sources.length && main) {
      sources.push({ src: main.src, alt: main.alt, cutout: stage.classList.contains("is-cutout") });
    }
    var index = 0;

    function show(i) {
      index = (i + sources.length) % sources.length;
      if (main) {
        main.src = sources[index].src;
        main.alt = sources[index].alt;
        stage.classList.toggle("is-cutout", sources[index].cutout);
      }
      thumbs.forEach(function (t, n) {
        t.setAttribute("aria-current", String(n === index));
      });
    }

    thumbs.forEach(function (t, i) {
      t.addEventListener("click", function () { show(i); });
    });

    var box = $("#lightbox");
    if (!box || !main) return;
    var boxImg = $("img", box);
    var lastFocus = null;

    function open() {
      lastFocus = document.activeElement;
      boxImg.src = sources[index].src;
      boxImg.alt = sources[index].alt;
      box.hidden = false;
      document.body.style.overflow = "hidden";
      $(".lightbox__close", box).focus();
    }

    function close() {
      box.hidden = true;
      document.body.style.overflow = "";
      if (lastFocus) lastFocus.focus();
    }

    function step(delta) {
      show(index + delta);
      boxImg.src = sources[index].src;
      boxImg.alt = sources[index].alt;
    }

    main.addEventListener("click", open);
    $(".lightbox__close", box).addEventListener("click", close);
    $(".lightbox__nav--prev", box).addEventListener("click", function () { step(-1); });
    $(".lightbox__nav--next", box).addEventListener("click", function () { step(1); });
    box.addEventListener("click", function (e) {
      if (e.target === box) close();
    });
    document.addEventListener("keydown", function (e) {
      if (box.hidden) return;
      if (e.key === "Escape") close();
      if (e.key === "ArrowLeft") step(-1);
      if (e.key === "ArrowRight") step(1);
    });

    show(0);
  }

  /* --- Фильтры и сортировка каталога ------------------------- */

  function initCatalog() {
    var root = $("[data-catalog]");
    if (!root) return;

    var grid = $("[data-catalog-grid]", root);
    var cards = $$(".machine-card", grid);
    var counter = $("[data-catalog-count]", root);
    var empty = $("[data-catalog-empty]", root);
    var sort = $("[data-catalog-sort]", root);
    var reset = $("[data-catalog-reset]", root);
    var boxes = $$("input[type=checkbox][data-filter]", root);

    function matches(card) {
      var groups = {};
      boxes.forEach(function (box) {
        if (!box.checked) return;
        var key = box.dataset.filter;
        (groups[key] = groups[key] || []).push(box.value);
      });
      return Object.keys(groups).every(function (key) {
        return groups[key].indexOf(card.dataset[key] || "") !== -1;
      });
    }

    function apply() {
      var shown = 0;
      cards.forEach(function (card) {
        var ok = matches(card);
        card.classList.toggle("is-hidden", !ok);
        if (ok) shown += 1;
      });
      if (counter) counter.textContent = plural(shown, ["модель", "модели", "моделей"]);
      if (empty) empty.hidden = shown > 0;
    }

    var ORDER = {
      name: function (a, b) { return a.dataset.name.localeCompare(b.dataset.name, "ru"); },
      massAsc: function (a, b) { return num(a, "mass") - num(b, "mass"); },
      massDesc: function (a, b) { return num(b, "mass") - num(a, "mass"); },
      powerDesc: function (a, b) { return num(b, "power") - num(a, "power"); },
    };

    function num(card, key) {
      return parseFloat(card.dataset[key]) || 0;
    }

    function applySort() {
      var compare = ORDER[sort && sort.value];
      if (!compare) return;
      cards.slice().sort(compare).forEach(function (card) { grid.appendChild(card); });
    }

    boxes.forEach(function (box) { box.addEventListener("change", apply); });
    if (sort) sort.addEventListener("change", applySort);
    if (reset) {
      reset.addEventListener("click", function () {
        boxes.forEach(function (box) { box.checked = false; });
        apply();
      });
    }

    apply();
  }

  function plural(n, forms) {
    var mod10 = n % 10;
    var mod100 = n % 100;
    var form = forms[2];
    if (mod10 === 1 && mod100 !== 11) form = forms[0];
    else if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) form = forms[1];
    return n + " " + form;
  }

  /* --- Телефонная маска -------------------------------------- */

  function initPhoneMask() {
    $$("input[type=tel]").forEach(function (input) {
      input.addEventListener("input", function () {
        var digits = input.value.replace(/\D/g, "");
        if (digits[0] === "8") digits = "7" + digits.slice(1);
        if (digits[0] !== "7") digits = "7" + digits;
        digits = digits.slice(0, 11);
        var out = "+7";
        if (digits.length > 1) out += " (" + digits.slice(1, 4);
        if (digits.length >= 4) out += ")";
        if (digits.length > 4) out += " " + digits.slice(4, 7);
        if (digits.length > 7) out += "-" + digits.slice(7, 9);
        if (digits.length > 9) out += "-" + digits.slice(9, 11);
        input.value = out;
      });
    });
  }

  /* --- Отправка форм ----------------------------------------- */

  function initForms() {
    var config = window.ALFA_CONFIG || {};

    $$("form[data-form]").forEach(function (form) {
      var status = $(".form__status", form);
      var submit = $("button[type=submit]", form);

      form.addEventListener("submit", function (e) {
        e.preventDefault();
        if (!validate(form)) return;

        var endpoint = config.formEndpoint;
        if (!endpoint || endpoint.indexOf("ВСТАВЬТЕ") !== -1) {
          say(status, "error",
            "Отправка форм ещё не подключена. Напишите нам на " +
            '<a href="mailto:' + config.email + "?subject=" +
            encodeURIComponent(form.dataset.subject || "Заявка с сайта") + '">' +
            config.email + "</a> или позвоните: " +
            '<a href="tel:' + (config.phoneHref || "") + '">' + config.phone + "</a>.");
          return;
        }

        if (submit) {
          submit.disabled = true;
          submit.dataset.label = submit.textContent;
          submit.textContent = "Отправляем…";
        }

        fetch(endpoint, {
          method: "POST",
          headers: { Accept: "application/json" },
          body: new FormData(form),
        })
          .then(function (res) {
            if (!res.ok) throw new Error("HTTP " + res.status);
            form.reset();
            say(status, "ok", "Заявка отправлена. Мы свяжемся с вами в рабочее время.");
          })
          .catch(function () {
            say(status, "error",
              "Не удалось отправить. Напишите на " +
              '<a href="mailto:' + config.email + '">' + config.email + "</a> или позвоните " +
              '<a href="tel:' + (config.phoneHref || "") + '">' + config.phone + "</a>.");
          })
          .finally(function () {
            if (submit) {
              submit.disabled = false;
              submit.textContent = submit.dataset.label;
            }
          });
      });
    });
  }

  function validate(form) {
    var ok = true;
    $$("[required]", form).forEach(function (field) {
      var error = field.closest(".field, .form__consent");
      var slot = error ? $(".field__error", error) : null;
      var bad = field.type === "checkbox" ? !field.checked : !field.value.trim();
      if (!bad && field.type === "email") bad = !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(field.value);
      if (!bad && field.type === "tel") bad = field.value.replace(/\D/g, "").length < 11;
      field.setAttribute("aria-invalid", String(bad));
      if (slot) slot.textContent = bad ? "Заполните это поле" : "";
      if (bad && ok) {
        field.focus();
        ok = false;
      }
    });
    return ok;
  }

  function say(node, kind, html) {
    if (!node) return;
    node.innerHTML = html;
    node.hidden = false;
    node.classList.toggle("form__status--error", kind === "error");
  }

  /* --- Запуск ------------------------------------------------- */

  function boot() {
    initNav();
    initTabs();
    initAccordion();
    initGallery();
    initCatalog();
    initPhoneMask();
    initForms();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
