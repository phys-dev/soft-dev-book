// Просмотрщик слайдов лекций. Масштабирует холст 1920×1080 под окно,
// переключает слайды и рисует стрелки <x-connector>: в формате слайдов это
// элемент редактора презентаций, и браузер сам его не отображает.
//
// Заметки докладчика лежат в скрытом <aside> каждого слайда; кнопка
// «Заметки докладчика» или клавиша N показывает заметки текущего слайда
// в панели под ним.
//
// Записи демонстраций в терминале приходят как <iframe data-srcdoc>.
// Запись загружается, только пока её слайд на экране: при каждом показе
// она проигрывается с начала и не расходует процессор на скрытых слайдах.
//
// Слайд хранится в адресе (#/id слайда), поэтому из главы книги можно
// открыть лекцию сразу на нужной части. Косая черта нужна, чтобы адрес не
// совпадал с id элемента: иначе браузер при загрузке прокручивает к слайду
// и страницу главы, в которую встроено окно.
(function () {
  "use strict";

  var W = 1920, H = 1080;
  var SVG = "http://www.w3.org/2000/svg";

  var stage = document.querySelector(".stage");
  var canvas = document.querySelector(".canvas");
  var slides = Array.prototype.slice.call(canvas.children).filter(function (el) {
    return el.tagName === "SECTION" && !el.hidden;
  });
  var current = -1;

  // Стрелки

  function num(value, fallback) {
    var n = parseFloat(value);
    return isNaN(n) ? fallback : n;
  }

  // Точки ломаной по маршруту: straight, hv (вбок, затем вниз), vh (вниз,
  // затем вбок), elbow (три отрезка с изломом посередине большего хода).
  function route(x1, y1, x2, y2, kind) {
    if (kind === "hv") return [[x1, y1], [x2, y1], [x2, y2]];
    if (kind === "vh") return [[x1, y1], [x1, y2], [x2, y2]];
    if (kind === "elbow") {
      if (Math.abs(x2 - x1) >= Math.abs(y2 - y1)) {
        var mx = (x1 + x2) / 2;
        return [[x1, y1], [mx, y1], [mx, y2], [x2, y2]];
      }
      var my = (y1 + y2) / 2;
      return [[x1, y1], [x1, my], [x2, my], [x2, y2]];
    }
    return [[x1, y1], [x2, y2]];
  }

  // Наконечник — «галочка» длиной около четырёх толщин линии в точке tip,
  // направленная от точки from.
  function head(tip, from, width) {
    var dx = tip[0] - from[0], dy = tip[1] - from[1];
    var len = Math.hypot(dx, dy) || 1;
    var ux = dx / len, uy = dy / len;
    var l = 4 * width, h = 2.2 * width;
    var bx = tip[0] - ux * l, by = tip[1] - uy * l;
    return "M" + (bx - uy * h) + " " + (by + ux * h) +
      " L" + tip[0] + " " + tip[1] +
      " L" + (bx + uy * h) + " " + (by - ux * h);
  }

  function drawConnector(el) {
    var s = el.style;
    var width = Math.min(num(s.borderWidth, 2), 32);
    var dash = s.borderStyle;
    var heads = el.getAttribute("head") || "end";
    var pinned = el.hasAttribute("x1");
    var pts;

    if (pinned) {
      pts = route(num(el.getAttribute("x1"), 0), num(el.getAttribute("y1"), 0),
                  num(el.getAttribute("x2"), 0), num(el.getAttribute("y2"), 0),
                  el.getAttribute("route") || "straight");
    } else {
      // стрелка в потоке идёт из угла своего блока в противоположный
      var fw = num(s.width, 0), fh = num(s.height, 0);
      var from = el.getAttribute("from") || "tl";
      var sx = from.charAt(1) === "r" ? fw : 0;
      var sy = from.charAt(0) === "b" ? fh : 0;
      pts = [[sx, sy], [fw - sx, fh - sy]];
    }

    var svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("aria-hidden", "true");
    svg.style.position = "absolute";
    svg.style.left = "0";
    svg.style.top = "0";
    svg.style.overflow = "visible";
    svg.style.pointerEvents = "none";
    if (pinned) {
      svg.style.width = "100%";
      svg.style.height = "100%";
    } else {
      svg.setAttribute("width", "1");
      svg.setAttribute("height", "1");
    }

    var paint = {
      fill: "none",
      stroke: s.color || "currentColor",
      "stroke-width": width,
      "stroke-linecap": "round",
      "stroke-linejoin": "round"
    };

    var line = document.createElementNS(SVG, "path");
    line.setAttribute("d", "M" + pts.map(function (p) { return p[0] + " " + p[1]; }).join(" L"));
    if (dash === "dashed") line.setAttribute("stroke-dasharray", 3 * width + " " + 2.5 * width);
    if (dash === "dotted") line.setAttribute("stroke-dasharray", "0 " + 2 * width);
    Object.keys(paint).forEach(function (k) { line.setAttribute(k, paint[k]); });
    svg.appendChild(line);

    // направление наконечника — по последнему отрезку ненулевой длины
    function tail(list) {
      var tip = list[list.length - 1];
      for (var i = list.length - 2; i >= 0; i--) {
        if (list[i][0] !== tip[0] || list[i][1] !== tip[1]) return [tip, list[i]];
      }
      return [tip, [tip[0] - 1, tip[1]]];
    }
    var tips = [];
    if (heads === "end" || heads === "both") tips.push(tail(pts));
    if (heads === "both") tips.push(tail(pts.slice().reverse()));
    tips.forEach(function (t) {
      var h = document.createElementNS(SVG, "path");
      h.setAttribute("d", head(t[0], t[1], width));
      Object.keys(paint).forEach(function (k) { h.setAttribute(k, paint[k]); });
      svg.appendChild(h);
    });

    if (pinned) {
      // закреплённая стрелка: координаты от блока с position:relative или
      // от слайда; svg занимает место элемента, чтобы сохранить порядок
      // наложения
      el.parentNode.replaceChild(svg, el);
    } else {
      el.style.position = "relative";
      el.appendChild(svg);
    }
  }

  Array.prototype.forEach.call(canvas.querySelectorAll("x-connector"), drawConnector);

  // Масштаб и показ слайда

  function fit() {
    var sw = stage.clientWidth, sh = stage.clientHeight;
    var k = Math.min(sw / W, sh / H);
    canvas.style.transform = "translate(" + (sw - W * k) / 2 + "px," +
      (sh - H * k) / 2 + "px) scale(" + k + ")";
  }

  var counter = document.querySelector(".counter");
  var prev = document.querySelector("[data-go='prev']");
  var next = document.querySelector("[data-go='next']");
  var full = document.querySelector("[data-go='full']");
  var out = document.querySelector("[data-go='out']");

  function embeds(el, on) {
    Array.prototype.forEach.call(el.querySelectorAll("iframe[data-srcdoc]"), function (f) {
      if (on) f.srcdoc = f.getAttribute("data-srcdoc");
      else f.removeAttribute("srcdoc");
    });
  }

  // Заметки докладчика

  var notes = document.querySelector(".notes");
  var notesButton = document.querySelector("[data-go='notes']");
  var embedded = window.self !== window.top;
  // метка раздела заметки в начале абзаца: «Изложение.», «Видео:»,
  // «Поправка к видео (0:42:42):» — выделяется полужирным
  var LABEL = /^((?:Время|Изложение|Демонстрации?|Для физиков|Вопросы? аудитории|Поправк[аи]|Уточнение|Замечание|Видео|Если спросят|Вывод для аудитории|Подготовка|Домашнее задание|Источники|Пример докладчика|Рекомендация докладчика)[^.:()]*(?:\([^)]*\))?[.:])(?=\s)/;

  function renderNotes() {
    if (notes.hidden) return;
    var aside = slides[current].querySelector("aside");
    var text = aside ? aside.textContent.trim() : "";
    notes.textContent = "";
    if (!text) {
      var empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "К этому слайду заметок нет.";
      notes.appendChild(empty);
    }
    text.split("\n").forEach(function (line) {
      line = line.trim();
      if (!line) return;
      var p = document.createElement("p");
      var m = LABEL.exec(line);
      if (m) {
        var label = document.createElement("strong");
        label.textContent = m[1];
        p.appendChild(label);
        line = line.slice(m[1].length);
      }
      p.appendChild(document.createTextNode(line));
      notes.appendChild(p);
    });
    notes.scrollTop = 0;
  }

  function toggleNotes(on) {
    notes.hidden = !on;
    notesButton.setAttribute("aria-pressed", String(on));
    // открытую панель помнит только отдельная страница: во встроенном
    // окне главы она занимала бы место слайда
    if (!embedded) {
      try { localStorage.setItem("slides-notes", on ? "1" : "0"); } catch (e) { /* хранилище недоступно */ }
    }
    renderNotes();
    fit();
  }

  function show(i) {
    i = Math.max(0, Math.min(slides.length - 1, i));
    if (i === current) return;
    if (current >= 0) {
      slides[current].classList.remove("current");
      embeds(slides[current], false);
    }
    current = i;
    slides[i].classList.add("current");
    embeds(slides[i], true);
    counter.textContent = (i + 1) + " / " + slides.length;
    prev.disabled = i === 0;
    next.disabled = i === slides.length - 1;
    // replaceState, а не новая запись: иначе кнопка «Назад» в книге
    // листала бы слайды во встроенном окне
    history.replaceState(null, "", "#/" + slides[i].id);
    out.href = location.href;
    renderNotes();
  }

  function fromHash() {
    var id = decodeURIComponent(location.hash.replace(/^#\/?/, ""));
    if (!id) return 0;
    for (var i = 0; i < slides.length; i++) if (slides[i].id === id) return i;
    var n = parseInt(id, 10);
    return isNaN(n) ? 0 : n - 1;
  }

  slides.forEach(function (el, i) {
    el.setAttribute("role", "group");
    el.setAttribute("aria-roledescription", "слайд");
    el.setAttribute("aria-label", (i + 1) + " из " + slides.length);
  });

  prev.addEventListener("click", function () { show(current - 1); });
  next.addEventListener("click", function () { show(current + 1); });

  if (!document.fullscreenEnabled) full.hidden = true;
  full.addEventListener("click", function () {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen();
  });

  // ссылка на отдельную вкладку нужна только во встроенном окне
  if (!embedded) out.hidden = true;

  if (!canvas.querySelector("section > aside")) notesButton.hidden = true;
  notesButton.addEventListener("click", function () { toggleNotes(notes.hidden); });
  if (!embedded && !notesButton.hidden) {
    try {
      if (localStorage.getItem("slides-notes") === "1") {
        notes.hidden = false;
        notesButton.setAttribute("aria-pressed", "true");
      }
    } catch (e) { /* хранилище недоступно */ }
  }

  document.addEventListener("keydown", function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    // буквенные клавиши — по положению, чтобы работали и в русской раскладке
    var key = e.code === "KeyN" ? "n" : e.code === "KeyF" ? "f" : e.key;
    switch (key) {
      case "ArrowRight": case "PageDown": case " ": show(current + 1); break;
      case "ArrowLeft": case "PageUp": show(current - 1); break;
      case "Home": show(0); break;
      case "End": show(slides.length - 1); break;
      case "f": case "F": if (!full.hidden) full.click(); return;
      case "n": case "N": if (!notesButton.hidden) toggleNotes(notes.hidden); return;
      default: return;
    }
    e.preventDefault();
  });

  // пролистывание пальцем на телефоне
  var touchX = null;
  stage.addEventListener("touchstart", function (e) { touchX = e.touches[0].clientX; }, { passive: true });
  stage.addEventListener("touchend", function (e) {
    if (touchX === null) return;
    var dx = e.changedTouches[0].clientX - touchX;
    touchX = null;
    if (Math.abs(dx) > 40) show(current + (dx < 0 ? 1 : -1));
  });

  // при печати на листах нужны все записи, после печати — только текущая
  window.addEventListener("beforeprint", function () {
    slides.forEach(function (el) { embeds(el, true); });
  });
  window.addEventListener("afterprint", function () {
    slides.forEach(function (el, i) { if (i !== current) embeds(el, false); });
  });

  window.addEventListener("hashchange", function () { show(fromHash()); });
  window.addEventListener("resize", fit);
  if (window.ResizeObserver) new ResizeObserver(fit).observe(stage);

  fit();
  show(fromHash());
})();
