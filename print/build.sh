#!/usr/bin/env bash
# Собирает оригинал-макет пособия: А4 (60x84 1/8), требования ИПЦ НГУ.
set -euo pipefail
cd "$(dirname "$0")/.."

TITLE="Разработка и применение программного обеспечения в физических исследованиях"
AUTHOR="В. В. Федоров"

echo "==> подготовка markdown"
python3 print/prepare.py

abstract=$(python3 -c "import sys; sys.path.insert(0,'print'); from prepare import VOLUMES; print(VOLUMES[None]['abstract'])")

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
    --metadata abstract="$abstract" \
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
  mv -f book.pdf "Разработка и применение ПО в физических исследованиях.pdf" )

pages=$(grep -oE 'Output written on [^(]*\([0-9]+ pages' print/build/book.log \
        | grep -oE '[0-9]+ pages$' | grep -oE '[0-9]+' | tail -1)
idx=$(grep -c '\\indexentry' print/build/book.idx 2>/dev/null || echo 0)
echo "    готово: $pages стр., меток указателя: $idx"
# схема ИПЦ для А4: страницы / 8 = уч.-изд. л.; х 0,93 = усл. печ. л.
python3 - "$pages" <<'PY'
import sys
p = int(sys.argv[1] or 0)
if p:
    print(f"    для выходных данных: {p/8:g} уч.-изд. л., {p/8*0.93:.1f} усл. печ. л.")
PY
