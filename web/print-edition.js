// Кнопка принтера в шапке по умолчанию ведёт на print.html — страницу со
// всей книгой сразу, которую браузер печатает как придётся: с обрезанными
// листингами и без вёрстки. Вместо этого отдаём готовое печатное издание,
// собранное под требования ИПЦ НГУ.
//
// Ссылка ведёт на latest, а не на конкретный тег: так после нового релиза
// сайт править не нужно.
(function () {
  var PDF = "https://github.com/phys-dev/soft-dev-book/releases/latest/download/soft-dev-book.pdf";
  var TITLE = "Скачать печатное издание (PDF, А4)";

  function retarget() {
    var icon = document.getElementById("print-button");
    if (!icon) return;                      // mdbook сменил разметку
    var link = icon.closest("a");
    if (!link) return;
    link.setAttribute("href", PDF);
    link.setAttribute("title", TITLE);
    link.setAttribute("aria-label", TITLE);
    link.setAttribute("target", "_blank");
    link.setAttribute("rel", "noopener");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", retarget);
  } else {
    retarget();
  }
})();
