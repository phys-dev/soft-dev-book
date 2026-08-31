#!/usr/bin/env bash
# Собирает оригинал-макет пособия: А4 (60x84 1/8), требования ИПЦ НГУ.
set -euo pipefail
cd "$(dirname "$0")/.."

TITLE="Разработка и применение программного обеспечения в физических исследованиях"
AUTHOR="В. В. Федоров"
OUT="Разработка и применение ПО в физических исследованиях.pdf"
ABSTRACT="Пособие вводит в рабочую среду и инженерные практики научной разработки: операционная система GNU/Linux, алгоритмы и структуры данных, устройство языка Python, жизненный цикл программы, сети и базы данных. Вторая половина посвящена данным физического эксперимента и производительности: обработка и визуализация массивов, машинное обучение и нейронные сети, профилирование, многопоточность, асинхронность и вычисления на графических ускорителях. Завершают книгу разбор реальных кодов, применяемых в институтах СО РАН, и задания для самостоятельной работы."

echo "==> подготовка markdown"
python3 print/prepare.py

echo "==> вёрстка PDF"
# pandoc отдаёт .tex, дальше три прохода xelatex: первый собирает метки
# указателя, xindy их сортирует по-русски, последние два подставляют
# номера страниц и выравнивают оглавление
( cd print/build && pandoc book.md \
    --from=markdown+pipe_tables+backtick_code_blocks+tex_math_dollars+raw_tex+autolink_bare_uris+lists_without_preceding_blankline \
    --to=latex \
    --template=../template.tex \
    --top-level-division=chapter \
    --toc --toc-depth=2 \
    --number-sections \
    --syntax-highlighting=tango \
    --resource-path=.:img \
    --metadata title="$TITLE" \
    --metadata author="$AUTHOR" \
    --metadata lang=ru \
    --metadata abstract="$ABSTRACT" \
    -o book.tex )

# xelatex возвращает ненулевой код и на безобидных предупреждениях,
# поэтому не связываем проходы через && — успех проверяем по файлу
( cd print/build
  xelatex -interaction=nonstopmode book.tex > /dev/null 2>&1 || true
  texindy -L russian -C utf8 -M ../ruindex.xdy \
    -o book.ind book.idx > /dev/null 2>&1 || true
  xelatex -interaction=nonstopmode book.tex > /dev/null 2>&1 || true
  xelatex -interaction=nonstopmode book.tex > /dev/null 2>&1 || true
  if [ ! -f book.pdf ]; then
    echo "    ОШИБКА: PDF не собран, смотри print/build/book.log" >&2
    exit 1
  fi
  mv -f book.pdf "$OUT" )

PAGES=$(grep -oE 'Output written on [^(]*\([0-9]+ pages' print/build/book.log \
        | grep -oE '[0-9]+ pages$' | grep -oE '[0-9]+' | tail -1)
IDX=$(grep -c '\\indexentry' print/build/book.idx 2>/dev/null || echo 0)
# схема ИПЦ для А4: страницы / 8 = уч.-изд. л.; х 0,93 = усл. печ. л.
echo "    готово: print/build/$OUT"
echo "    страниц: $PAGES, меток указателя: $IDX"
python3 - "$PAGES" <<'PY'
import sys
p = int(sys.argv[1] or 0)
if p:
    uch = p / 8
    usl = uch * 0.93
    print(f"    для выходных данных: {uch:g} уч.-изд. л., {usl:.1f} усл. печ. л.")
PY
