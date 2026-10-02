#!/usr/bin/env python3
"""Собирает страницу со слайдами лекции для электронной версии книги.

Слайды выгружаются из презентации: deck.json (порядок слайдов, название,
шрифты) и slides/<id>.html, по одному слайду в файле. На страницу слайды
попадают в порядке deck.json вместе с заметками докладчика (<aside>):
на слайде заметки скрыты, а просмотрщик по кнопке «Заметки докладчика»
или клавише N показывает их в панели под слайдом. Ключ --no-notes
собирает страницу без заметок.

На сайт попадает только публичная часть заметок: абзацы с метками
«Время», «Видео», «Вопрос аудитории», «Если спросят», «Поправка»,
«Замечание», «Источники», «Подготовка», «Стенд» и «… докладчика» нужны
лишь докладчику и остаются в презентации. Слайд stand (подготовка стенда)
на сайт не попадает. Если в публичных заметках остались таймкоды,
ссылки на докладчика исходной лекции или слова из локального списка
web/private-words.txt (по регулярному выражению в строке; файл в git
не хранится), сборка останавливается.

Показывает слайды общий просмотрщик
src/slides/viewer.js и viewer.css, поэтому страница кладётся в ту же
папку. Живые вставки <x-embed> (записи
демонстраций в терминале) становятся изолированными <iframe>: скрипты
в них разрешены, доступ к странице книги и к сети закрыт.

Картинки слайдов презентация хранит как загруженные файлы, и в слайде
стоит адрес /_blob/<id>. Файл assets.json в папке с deck.json сопоставляет
такие адреса файлам на диске (пути относительно этой папки), и картинки
встраиваются в страницу data:-адресами: страница и её PDF обходятся без
отдельных файлов. Картинка без записи в assets.json останавливает сборку.

Кнопка «Скачать PDF» на панели ведёт на файл soft-dev-book-<имя страницы>.pdf
(для lecture-01.html — soft-dev-book-lecture-01.pdf) в последнем релизе
на GitHub. PDF печатает из готовой страницы web/slides_pdf.py; файл
прикладывается к релизу под тем же именем, иначе ссылка не сработает.

    python3 web/slides.py <папка с deck.json> src/slides/lecture-01.html [--no-notes]

Страницу не правят вручную: правки вносятся в презентацию, после чего
страница собирается заново.
"""
import base64
import html
import json
import mimetypes
import os
import re
import sys

FONTS = "https://fonts.googleapis.com/css2?"
SLIDE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
EMBED = re.compile(r'<x-embed style="([^"]*)">(.*?)</x-embed>', re.S)
PRIVATE_NOTE = re.compile(
    r"^(?:Время|Видео|Вопросы? аудитории|Возможные вопросы|Если спросят|"
    r"Поправк[аи]|Уточнени[ея]|Замечание|Источники|Подготовка|Стенд|"
    r"[А-ЯЁ][а-яё]+ докладчика)\b")
PRESENTER_ONLY = {"stand"}
LEAKS = [re.compile(r"\b\d:\d\d:\d\d\b"), re.compile(r"докладчик", re.I)]
PRIVATE_WORDS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "private-words.txt")
# как и в редакторе презентаций: вставке доступны только собственные
# встроенные скрипты и стили, сеть закрыта
EMBED_CSP = ('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
             'script-src \'unsafe-inline\'; style-src \'unsafe-inline\'; font-src data:">')
# при печати браузер иначе заменяет тёмный фон записи белым, а светлый
# текст — тёмным
EMBED_PRINT = ('<style>html{-webkit-print-color-adjust:exact;'
               'print-color-adjust:exact}</style>')
# PDF слайдов лежат в последнем релизе книги
RELEASE = "https://github.com/phys-dev/soft-dev-book/releases/latest/download/"

ICON = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="{}" fill="none" '
        'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" '
        'stroke-linejoin="round"/></svg>')
ICONS = {
    "prev": "M15 5l-7 7 7 7",
    "next": "M9 5l7 7-7 7",
    "out": "M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7"
           "a1 1 0 0 1 1-1h5",
    "full": "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5",
    "notes": "M6 3h12v18H6zM9 8h6M9 12h6M9 16h4",
    "pdf": "M12 4v11M7 10l5 5 5-5M5 20h14",
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
<div class="notes" id="notes" role="region" aria-label="Заметки докладчика" hidden></div>
<nav class="bar" aria-label="Управление слайдами">
<span></span>
<span class="nav">
<button type="button" data-go="prev" aria-label="Предыдущий слайд" title="Предыдущий слайд (←)">{prev}</button>
<span class="counter" aria-live="polite"></span>
<button type="button" data-go="next" aria-label="Следующий слайд" title="Следующий слайд (→)">{next}</button>
</span>
<span class="tools">
<a data-go="out" href="#" target="_blank" rel="noopener" aria-label="Открыть в отдельной вкладке" title="Открыть в отдельной вкладке">{out}</a>
<a data-go="pdf" href="{pdf_href}" target="_blank" rel="noopener" aria-label="Скачать слайды в PDF" title="Скачать слайды в PDF">{pdf}</a>
<button type="button" data-go="notes" aria-controls="notes" aria-pressed="false" aria-label="Заметки докладчика" title="Заметки докладчика (N)">{notes}</button>
<button type="button" data-go="full" aria-label="Во весь экран" title="Во весь экран (F)">{full}</button>
</span>
</nav>
<script src="viewer.js"></script>
</body>
</html>
"""


BLOB = re.compile(r'src="(/_blob/[^"]+)"')


def blob_files(folder):
    """Соответствие адресов /_blob/<id> файлам на диске: assets.json рядом с deck.json."""
    path = os.path.join(folder, "assets.json")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def inline_images(text, folder, files):
    """Картинки /_blob/<id> встраиваются в слайд data:-адресами."""
    def repl(match):
        url = match.group(1)
        if url not in files:
            sys.exit(f"нет файла для картинки {url}: допишите assets.json в {folder}")
        path = os.path.join(folder, files[url])
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        return f'src="data:{mime};base64,{data}"'
    return BLOB.sub(repl, text)


def deck_folder(path):
    """Папка с deck.json: указанная или её подпапка project/."""
    for folder in (path, os.path.join(path, "project")):
        if os.path.isfile(os.path.join(folder, "deck.json")):
            return folder
    sys.exit(f"нет deck.json в {path}")


def embed(match):
    """Вставка <x-embed> в виде <iframe>. Страницу вставки просмотрщик
    загружает из data-srcdoc, только пока слайд на экране."""
    style, page = match.groups()
    page = (page.replace("<head>", "<head>" + EMBED_CSP + EMBED_PRINT, 1) if "<head>" in page
            else EMBED_CSP + EMBED_PRINT + page)
    return (f'<iframe class="embed" sandbox="allow-scripts" '
            f'title="Запись демонстрации в терминале" style="{style}" '
            f'data-srcdoc="{html.escape(page)}"></iframe>')


def public_notes(text):
    """Заметки без абзацев, которые нужны только докладчику."""
    return "\n".join(p for p in text.split("\n")
                     if p.strip() and not PRIVATE_NOTE.match(p.strip()))


def private_words():
    """Слова из локального списка, которых не должно быть в заметках."""
    if not os.path.isfile(PRIVATE_WORDS):
        return []
    with open(PRIVATE_WORDS, encoding="utf-8") as f:
        return [re.compile(line.strip(), re.I) for line in f
                if line.strip() and not line.startswith("#")]


def check_notes(page):
    """Останавливает сборку, если в публичных заметках осталось лишнее."""
    patterns = LEAKS + private_words()
    found = []
    for slide_id, notes in re.findall(
            r'<section id="([^"]+)".*?<aside hidden>(.*?)</aside>', page, re.S):
        text = html.unescape(notes)
        found += [f"{slide_id}: {m.group(0)}" for p in patterns
                  for m in p.finditer(text)]
    if found:
        sys.exit("в заметках остались сведения только для докладчика:\n  "
                 + "\n  ".join(found))


def slide(folder, slide_id, notes=True, files=None):
    """Один слайд без служебных комментариев; заметки докладчика скрыты
    (hidden) или, при notes=False, удалены."""
    if not SLIDE_ID.match(slide_id):
        sys.exit(f"недопустимый id слайда: {slide_id!r}")
    with open(os.path.join(folder, "slides", slide_id + ".html"),
              encoding="utf-8") as f:
        text = f.read()
    if notes:
        text = re.sub(r"<aside>(.*?)</aside>",
                      lambda m: f"<aside hidden>{public_notes(m.group(1))}</aside>",
                      text, flags=re.S)
    else:
        text = re.sub(r"<aside>.*?</aside>", "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->\n?", "", text, flags=re.S).strip()
    if (not text.startswith(f'<section id="{slide_id}"')
            or text.count("<section") != 1 or not text.endswith("</section>")):
        sys.exit(f"{slide_id}.html: ожидается ровно один <section id=\"{slide_id}\">")
    return EMBED.sub(embed, inline_images(text, folder, files or {}))


def pdf_name(page_path):
    """Имя PDF в релизе: soft-dev-book-lecture-01.pdf для lecture-01.html."""
    return "soft-dev-book-" + os.path.splitext(os.path.basename(page_path))[0] + ".pdf"


def build(folder, pdf_href, notes=True):
    with open(os.path.join(folder, "deck.json"), encoding="utf-8") as f:
        deck = json.load(f)
    fonts = [f'<link rel="stylesheet" href="{html.escape(face["href"])}">'
             for face in deck.get("faces", {}).values()
             if face.get("href", "").startswith(FONTS)]
    files = blob_files(folder)
    slides = [slide(folder, slide_id, notes, files) for slide_id in deck["order"]
              if slide_id not in PRESENTER_ONLY]
    icons = {name: ICON.format(d) for name, d in ICONS.items()}
    page = PAGE.format(title=html.escape(deck["title"]), fonts="\n".join(fonts),
                       slides="\n".join(slides), pdf_href=html.escape(pdf_href), **icons)
    return page, len(slides)


def main():
    args = [a for a in sys.argv[1:] if a != "--no-notes"]
    if len(args) != 2:
        sys.exit(__doc__)
    page, count = build(deck_folder(args[0]), RELEASE + pdf_name(args[1]),
                        notes="--no-notes" not in sys.argv)
    check_notes(page)
    with open(args[1], "w", encoding="utf-8") as f:
        f.write(page)
    print(f"{args[1]}: {count} слайдов, {len(page.encode()) // 1024} КБ")


if __name__ == "__main__":
    main()
