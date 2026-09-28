#!/usr/bin/env python3
"""Собирает страницу со слайдами лекции для электронной версии книги.

Слайды выгружаются из презентации: deck.json (порядок слайдов, название,
шрифты) и slides/<id>.html, по одному слайду в файле. На страницу слайды
попадают в порядке deck.json без заметок докладчика (<aside>): в заметках
ответы на вопросы аудитории и тайминг, читателю они не нужны. Показывает
слайды общий просмотрщик src/slides/viewer.js и viewer.css, поэтому
страница кладётся в ту же папку.

    python3 web/slides.py <папка с deck.json> src/slides/lecture-01.html

Страницу не правят вручную: правки вносятся в презентацию, после чего
страница собирается заново.
"""
import html
import json
import os
import re
import sys

FONTS = "https://fonts.googleapis.com/css2?"
SLIDE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

ICON = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="{}" fill="none" '
        'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" '
        'stroke-linejoin="round"/></svg>')
ICONS = {
    "prev": "M15 5l-7 7 7 7",
    "next": "M9 5l7 7-7 7",
    "out": "M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7"
           "a1 1 0 0 1 1-1h5",
    "full": "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5",
}

PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<!-- Собрано web/slides.py из презентации. Вручную не править: правки
     вносятся в презентацию, затем страница собирается заново. -->
{fonts}
<link rel="stylesheet" href="viewer.css">
</head>
<body>
<div class="stage">
<div class="canvas">
{slides}
</div>
</div>
<nav class="bar" aria-label="Управление слайдами">
<span></span>
<span class="nav">
<button type="button" data-go="prev" aria-label="Предыдущий слайд" title="Предыдущий слайд (←)">{prev}</button>
<span class="counter" aria-live="polite"></span>
<button type="button" data-go="next" aria-label="Следующий слайд" title="Следующий слайд (→)">{next}</button>
</span>
<span class="tools">
<a data-go="out" href="#" target="_blank" rel="noopener" aria-label="Открыть в отдельной вкладке" title="Открыть в отдельной вкладке">{out}</a>
<button type="button" data-go="full" aria-label="Во весь экран" title="Во весь экран (F)">{full}</button>
</span>
</nav>
<script src="viewer.js"></script>
</body>
</html>
"""


def deck_folder(path):
    """Папка с deck.json: указанная или её подпапка project/."""
    for folder in (path, os.path.join(path, "project")):
        if os.path.isfile(os.path.join(folder, "deck.json")):
            return folder
    sys.exit(f"нет deck.json в {path}")


def slide(folder, slide_id):
    """Один слайд без заметок докладчика и служебных комментариев."""
    if not SLIDE_ID.match(slide_id):
        sys.exit(f"недопустимый id слайда: {slide_id!r}")
    with open(os.path.join(folder, "slides", slide_id + ".html"),
              encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r"<aside>.*?</aside>", "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->\n?", "", text, flags=re.S).strip()
    if (not text.startswith(f'<section id="{slide_id}"')
            or text.count("<section") != 1 or not text.endswith("</section>")):
        sys.exit(f"{slide_id}.html: ожидается ровно один <section id=\"{slide_id}\">")
    return text


def build(folder):
    with open(os.path.join(folder, "deck.json"), encoding="utf-8") as f:
        deck = json.load(f)
    fonts = [f'<link rel="stylesheet" href="{html.escape(face["href"])}">'
             for face in deck.get("faces", {}).values()
             if face.get("href", "").startswith(FONTS)]
    slides = [slide(folder, slide_id) for slide_id in deck["order"]]
    icons = {name: ICON.format(d) for name, d in ICONS.items()}
    page = PAGE.format(title=html.escape(deck["title"]), fonts="\n".join(fonts),
                       slides="\n".join(slides), **icons)
    return page, len(slides)


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    page, count = build(deck_folder(sys.argv[1]))
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(page)
    print(f"{sys.argv[2]}: {count} слайдов, {len(page.encode()) // 1024} КБ")


if __name__ == "__main__":
    main()
