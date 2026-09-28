#!/usr/bin/env python3
"""Печатает страницу со слайдами лекции в PDF для релиза книги.

Страница, собранная web/slides.py, печатается браузером Chromium без окна
по правилам печати из viewer.css: по слайду на лист 1920×1080, без панели
управления и без заметок. Записи демонстраций в терминале просмотрщик
загружает, только пока слайд на экране, а перед печатью — по событию
beforeprint. Браузер без окна этого события не посылает, поэтому печатается
временная копия страницы, которая посылает его сама.

    python3 web/slides_pdf.py src/slides/lecture-01.html print/build/soft-dev-book-lecture-01.pdf

Имя файла должно совпадать с тем, на которое ведёт кнопка «Скачать PDF»
(soft-dev-book-<имя страницы>.pdf, см. web/slides.py): PDF прикладывается
к последнему релизу под этим именем. Путь к браузеру задаёт переменная
CHROMIUM; без неё ищутся Google Chrome, Chromium и браузер Playwright.
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

TRIGGER = '<script>window.dispatchEvent(new Event("beforeprint"));</script>'
CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    *sorted(glob.glob(os.path.expanduser(
        "~/Library/Caches/ms-playwright/chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium")),
        reverse=True),
    *sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux/chrome")),
            reverse=True),
]


def chromium():
    for path in [os.environ.get("CHROMIUM")] + CANDIDATES:
        if path and os.path.isfile(path):
            return path
    for name in ("chromium", "chromium-browser", "google-chrome"):
        if shutil.which(name):
            return shutil.which(name)
    sys.exit("не найден Chromium: укажите путь в переменной CHROMIUM")


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    page_path, pdf_path = sys.argv[1], os.path.abspath(sys.argv[2])
    with open(page_path, encoding="utf-8") as f:
        page = f.read()
    if '<script src="viewer.js"></script>' not in page:
        sys.exit(f"{page_path}: не похоже на страницу web/slides.py")
    slides = len(re.findall(r'<section id="', page))
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name in ("viewer.js", "viewer.css"):
            shutil.copy(os.path.join(os.path.dirname(os.path.abspath(page_path)), name), tmp)
        copy = os.path.join(tmp, "print.html")
        with open(copy, "w", encoding="utf-8") as f:
            f.write(page.replace('<script src="viewer.js"></script>',
                                 '<script src="viewer.js"></script>\n' + TRIGGER, 1))
        # запас виртуального времени — на шрифты и загрузку записей
        subprocess.run([chromium(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        "--virtual-time-budget=20000", "--print-to-pdf=" + pdf_path,
                        "file://" + copy], check=True, capture_output=True)
    with open(pdf_path, "rb") as f:
        data = f.read()
    pages = len(re.findall(rb"/Type\s*/Page(?![s\w])", data))
    if pages != slides:
        sys.exit(f"{pdf_path}: {pages} листов вместо {slides}")
    print(f"{pdf_path}: {pages} листов, {len(data) // 1024} КБ")


if __name__ == "__main__":
    main()
