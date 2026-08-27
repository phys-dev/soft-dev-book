#!/usr/bin/env python3
"""Готовит markdown книги к вёрстке печатного пособия.

Собирает главы в порядке SUMMARY.md, приводит уровни заголовков,
вычищает интерактивный HTML (Plotly, pandas-таблицы), извлекает
картинки из base64 и переводит SVG в PDF для XeLaTeX.
"""
import base64
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
BUILD = os.path.join(ROOT, "print", "build")
IMG = os.path.join(BUILD, "img")

# Главы, которые не входят в печатное издание
SKIP = set()


def parse_summary():
    """Возвращает список элементов оглавления: (тип, заголовок, путь, уровень)."""
    path = os.path.join(SRC, "SUMMARY.md")
    items = []
    for line in io.open(path, encoding="utf-8"):
        part = re.match(r"^# (.+)$", line.strip())
        if part:
            items.append(("part", part.group(1).strip(), None, 0))
            continue
        link = re.match(r"^(\s*)[-*] \[([^\]]+)\]\((\./[^)]+)\)", line)
        if link:
            level = len(link.group(1)) // 2
            items.append(("chapter", link.group(2), link.group(3), level))
            continue
        front = re.match(r"^\[([^\]]+)\]\((\./[^)]+)\)", line.strip())
        if front:
            items.append(("front", front.group(1), front.group(2), 0))
    return items


def strip_html(text):
    """Убирает интерактивный HTML: скрипты Plotly, стили, pandas-таблицы."""
    # <div> с pandas-таблицами и стилями превращаем в отметку
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.S)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.S)
    # HTML-таблицы pandas -> markdown-таблица (упрощённо: только шапка и данные)
    text = re.sub(r"<div>\s*(<table.*?</table>)\s*</div>", _table_to_md,
                  text, flags=re.S)
    text = re.sub(r"<table.*?</table>", _table_to_md_raw, text, flags=re.S)
    # висячие div и прочие теги
    text = re.sub(r"</?div[^>]*>", "", text)
    text = re.sub(r"^\s*window\..*$", "", text, flags=re.M)
    text = re.sub(r"^\s*require\(\[.*$", "", text, flags=re.M)
    text = re.sub(r"^\s*if \(window\.MathJax.*$", "", text, flags=re.M)
    return text


MAX_CELL = 16


def _cells(row):
    """Содержимое ячеек строки таблицы; длинные значения обрезаем.

    В выводах pandas попадаются ячейки в сотни символов — в книжной
    полосе набора шириной 115 мм такая таблица уезжает за поля.
    """
    out = []
    for cell in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, flags=re.S):
        text = re.sub(r"<[^>]+>", "", cell).strip()
        text = re.sub(r"\s+", " ", text)
        if len(text) > MAX_CELL:
            text = text[:MAX_CELL - 1] + "…"
        out.append(text.replace("|", r"\|"))
    return out


def _table_html_to_md(html, max_rows=12, max_cols=7):
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.S)
    if not rows:
        return ""
    parsed = [_cells(r) for r in rows]
    parsed = [p for p in parsed if p]
    if not parsed:
        return ""
    width = min(max(len(p) for p in parsed), max_cols)
    truncated = len(parsed) > max_rows + 1
    head, body = parsed[0], parsed[1:max_rows + 1]
    head = (head + [""] * width)[:width]
    out = ["", "| " + " | ".join(head) + " |",
           "|" + "|".join(["---"] * width) + "|"]
    for row in body:
        row = (row + [""] * width)[:width]
        out.append("| " + " | ".join(row) + " |")
    if truncated:
        out.append("")
        out.append("*(таблица приведена частично)*")
    out.append("")
    return "\n".join(out)


def _table_to_md(match):
    return _table_html_to_md(match.group(1))


def _table_to_md_raw(match):
    return _table_html_to_md(match.group(0))


def extract_base64_images(text, prefix):
    """Сохраняет base64-картинки из <img> в файлы, возвращает markdown-ссылки.

    Встречаются и png, и svg+xml (графики HoloViews); svg сразу переводим в pdf.
    """
    def repl(match):
        mime, payload = match.group(1), match.group(2)
        try:
            data = base64.b64decode(re.sub(r"\s+", "", payload))
        except Exception:
            return ""
        digest = hashlib.md5(data).hexdigest()[:10]
        if "svg" in mime:
            svg = os.path.join(IMG, f"{prefix}-{digest}.svg")
            with open(svg, "wb") as f:
                f.write(data)
            name = f"{prefix}-{digest}.pdf"
            try:
                subprocess.run(["rsvg-convert", "-f", "pdf", "-o",
                                os.path.join(IMG, name), svg],
                               check=True, capture_output=True)
            except subprocess.CalledProcessError:
                return ""
            finally:
                os.remove(svg)
        else:
            ext = "png" if "png" in mime else "jpg"
            name = f"{prefix}-{digest}.{ext}"
            with open(os.path.join(IMG, name), "wb") as f:
                f.write(data)
        return f"\n\n![](img/{name})\n\n"

    pattern = (r"""<img[^>]*src=['"]data:image/"""
               r"""(png|jpeg|jpg|svg\+xml);base64,\s*([^'"]+)['"][^>]*/?>""")
    return re.sub(pattern, repl, text, flags=re.S)


def convert_svg(svg_path):
    """Переводит SVG в PDF для XeLaTeX, возвращает имя файла."""
    name = hashlib.md5(svg_path.encode()).hexdigest()[:10] + ".pdf"
    out = os.path.join(IMG, name)
    if not os.path.exists(out):
        subprocess.run(["rsvg-convert", "-f", "pdf", "-o", out, svg_path],
                       check=True, capture_output=True)
    return name


def fix_images(text, chapter_dir):
    """Приводит пути картинок к каталогу сборки, конвертирует SVG."""
    def repl(match):
        alt, target = match.group(1), match.group(2).strip()
        if target.startswith("http"):
            return ""                      # внешние картинки в печать не берём
        if target.startswith("img/"):
            return match.group(0)          # уже обработана
        path = os.path.normpath(os.path.join(chapter_dir, target))
        if not os.path.exists(path):
            return ""
        if path.lower().endswith(".svg"):
            try:
                return f"![{alt}](img/{convert_svg(path)})"
            except subprocess.CalledProcessError:
                return ""
        if path.lower().endswith(".gif"):
            return ""                      # анимацию не печатаем
        name = hashlib.md5(path.encode()).hexdigest()[:10] + os.path.splitext(path)[1]
        dst = os.path.join(IMG, name)
        if not os.path.exists(dst):
            shutil.copy(path, dst)
        return f"![{alt}](img/{name})"

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl, text)


def fix_math(text):
    """Приводит формулы mdbook к обычному TeX.

    1. \\( \\) -> $ $, \\[ \\] -> $$ $$. Пробелы внутри долларов убираем:
       pandoc не считает формулой конструкцию вида "$ x $".
    2. Убираем вложенные окружения equation внутри $$ ... $$ — MathJax это
       терпит, а LaTeX считает ошибкой.
    """
    text = re.sub(r"\\\\\((.+?)\\\\\)",
                  lambda m: "$" + m.group(1).strip() + "$", text, flags=re.S)
    text = re.sub(r"\\\\\[(.+?)\\\\\]",
                  lambda m: "\n$$" + m.group(1).strip() + "$$\n", text, flags=re.S)

    def unwrap(match):
        body = match.group(1)
        body = re.sub(r"\\(?:begin|end)\{equation\*?\}", "", body)
        body = re.sub(r"\\(?:begin|end)\{align\*?\}", "", body)
        # пустая строка внутри $$ разрывает формулу — pandoc видит новый абзац
        body = re.sub(r"\n\s*\n+", "\n", body)
        return "$$" + body.strip("\n") + "$$"

    return re.sub(r"\$\$(.+?)\$\$", unwrap, text, flags=re.S)


def fix_unicode(text):
    """Готовит текст к печати: убирает эмодзи и чинит символы вне шрифта.

    В печатном издании эмодзи не нужны (их нет в Times New Roman), а
    математические знаки, набранные в прозе как обычные символы, нужно
    перевести в формулы — иначе XeLaTeX их не найдёт.
    """
    # эмодзи и декоративные пиктограммы
    emoji = ("[\U0001F000-\U0001FAFF\U00002600-\U000027BF"
             "\U0001F1E6-\U0001F1FF\U0000FE0F\U00002B00-\U00002BFF]")
    text = re.sub(emoji + r"\s*", "", text)

    # одиночные математические знаки в прозе -> формулы
    def to_math(match):
        return "$\\" + {"∈": "in", "∉": "notin", "≈": "approx", "≤": "le",
                       "≥": "ge", "≠": "ne", "→": "to", "∞": "infty"}[match.group(0)] + "$"

    parts, out, in_fence = text.split("\n"), [], False
    for line in parts:
        if line.startswith("```"):
            in_fence = not in_fence
        elif not in_fence and not line.startswith("    "):
            line = re.sub(r"[∈∉≈≤≥≠→∞]", to_math, line)
        out.append(line)
    text = "\n".join(out)

    # голая кириллица внутри формул -> \text{...}
    def wrap_cyrillic(match):
        body = match.group(2)
        if "\\text{" in body:
            # уже частично обёрнуто — трогаем только то, что вне \text{}
            pieces = re.split(r"(\\text\{[^{}]*\})", body)
            body = "".join(p if p.startswith("\\text{")
                           else re.sub(r"[А-Яа-яЁё]+", r"\\text{\g<0>}", p)
                           for p in pieces)
        else:
            body = re.sub(r"[А-Яа-яЁё]+", r"\\text{\g<0>}", body)
        return match.group(1) + body + match.group(1)

    text = re.sub(r"(\$\$?)((?:[^$]|\$(?=\$))+?)\1", wrap_cyrillic, text, flags=re.S)
    return text


# ссылки, текст которых без адреса ничего не значит на бумаге
VAGUE_LINKS = {"здесь", "тут", "сюда", "ссылка", "по ссылке", "here",
               "link", "этой ссылке", "документация", "docs", "репозиторий"}


def fix_links(text):
    """Приводит ссылки к виду, пригодному для бумаги.

    Относительные ссылки на другие главы заменяем их названием — в печати
    переходить всё равно некуда. У внешних ссылок с невнятным текстом
    («здесь», «тут») дописываем адрес, иначе на бумаге он пропадёт.
    """
    def repl(match):
        title, target = match.group(1), match.group(2)
        if not target.startswith("http"):
            return title
        if title.strip().lower().strip(".,:;") in VAGUE_LINKS:
            return f"{title} ({target})"
        return match.group(0)

    return re.sub(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)\)", repl, text)


def shift_headings(text, base):
    """Сдвигает заголовки главы так, чтобы верхний стал уровня base."""
    levels = [len(m.group(1)) for m in re.finditer(r"^(#{1,6}) ", text, flags=re.M)]
    if not levels:
        return text
    shift = base - min(levels)
    if shift == 0:
        return text

    def repl(match):
        level = min(len(match.group(1)) + shift, 6)
        return "#" * max(level, 1) + " "
    return re.sub(r"^(#{1,6}) ", repl, text, flags=re.M)


def strip_manual_numbering(text):
    """Убирает ручную нумерацию из заголовков.

    В электронной версии заголовки не нумеруются автоматически, поэтому
    «1. Процессы», «2. Планировщик» читаются как список. В книге разделы
    нумерует LaTeX, и такой заголовок превращается в «2.3.2 1. Процессы» —
    номер задваивается.
    """
    return re.sub(r"^(#{2,6}) +\d+(?:\.\d+)*\.? +(?=\S)", r"\1 ",
                  text, flags=re.M)


def clean_output_blocks(text):
    """Ограничивает длину блоков вывода — в печати они занимают страницы."""
    lines, out, buf = text.split("\n"), [], []

    def flush():
        if not buf:
            return
        if len(buf) > 14:
            out.extend(buf[:12])
            out.append("    ... (вывод сокращён)")
        else:
            out.extend(buf)
        buf.clear()

    in_fence = False
    for line in lines:
        if line.startswith("```"):
            flush()
            in_fence = not in_fence
            out.append(line)
            continue
        if not in_fence and line.startswith("    ") and line.strip():
            buf.append(line)
            continue
        flush()
        out.append(line)
    flush()
    return "\n".join(out)


def main():
    os.makedirs(IMG, exist_ok=True)
    parts = []
    stats = []
    for kind, title, path, level in parse_summary():
        if kind == "part":
            parts.append(f"\n\n# {title}\n\n")
            continue
        if path is None or path in SKIP:
            continue
        full = os.path.normpath(os.path.join(SRC, path[2:]))
        if not os.path.exists(full):
            print(f"  пропуск (нет файла): {path}", file=sys.stderr)
            continue
        text = io.open(full, encoding="utf-8").read()
        before = len(text)
        text = strip_html(text)
        text = extract_base64_images(text, os.path.basename(full)[:-3])
        text = fix_images(text, os.path.dirname(full))
        text = fix_math(text)
        text = fix_unicode(text)
        text = fix_links(text)
        text = clean_output_blocks(text)
        text = strip_manual_numbering(text)
        # уровень: front-matter и главы верхнего уровня -> ##, вложенные -> ###
        text = shift_headings(text, 2 + level)
        if kind == "front":
            # «О книге» и «О себе» идут до частей — не нумеруем их,
            # иначе pandoc заводит фантомную главу 0.
            text = re.sub(r"^#+ .*$", f"## {title} {{.unnumbered}}",
                          text, count=1, flags=re.M)
        parts.append(text.strip() + "\n\n")
        stats.append((path, before, len(text)))

    note = """## От автора к печатному изданию {.unnumbered}

У этой книги есть постоянно обновляемая электронная версия:
**https://phys-dev.github.io/soft-dev-book/**

Печатное издание отличается от неё в трёх мелочах, о которых стоит знать
заранее.

Во-первых, длинные распечатки результатов работы программ здесь сокращены
до первых строк — полный вывод занял бы десятки страниц, не добавив ничего
к пониманию. Такие места помечены строкой `... (вывод сокращён)`.

Во-вторых, интерактивные графики, построенные библиотеками Plotly и
HoloViews, на бумаге показать невозможно: в электронной версии их можно
крутить, приближать и наводить курсор на точки, а здесь остался только
код, которым они строятся. Все статические иллюстрации (Matplotlib,
Seaborn) на месте.

В-третьих, перекрёстные ссылки между главами в бумажной версии приведены
просто названиями глав — ищи их по оглавлению.

Замечания, опечатки и предложения присылай в issues репозитория
**https://github.com/phys-dev/soft-dev-book** или в Telegram-канал
**https://t.me/physdev**.

"""
    # примечание ставим сразу после «О книге» и «О себе», до первой части
    first_part = next((i for i, p in enumerate(parts) if p.startswith("\n\n# ")), 0)
    parts.insert(first_part, note)

    book = "".join(parts)
    # схлопываем лишние пустые строки
    book = re.sub(r"\n{4,}", "\n\n\n", book)
    out = os.path.join(BUILD, "book.md")
    io.open(out, "w", encoding="utf-8").write(book)
    print(f"собрано глав: {len(stats)}")
    print(f"размер: {len(book) / 1024:.0f} КБ -> {out}")
    print(f"картинок: {len(os.listdir(IMG))}")
    biggest = sorted(stats, key=lambda s: -s[2])[:5]
    print("самые объёмные главы после очистки:")
    for path, b, a in biggest:
        print(f"  {a / 1024:7.0f} КБ (было {b / 1024:.0f}) {path}")


if __name__ == "__main__":
    main()
