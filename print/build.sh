#!/usr/bin/env bash
# Собирает оригинал-макет пособия: А4 (60x84 1/8), требования ИПЦ НГУ.
# Без аргументов собирает обе части; можно указать номер: build.sh 1
set -euo pipefail
cd "$(dirname "$0")/.."

TITLE="Разработка и применение программного обеспечения в физических исследованиях"
AUTHOR="В. В. Федоров"

build_volume() {
  local vol="$1" name="$2"
  echo "==> Часть $vol. $name — подготовка markdown"
  python3 print/prepare.py "$vol"

  local abstract
  abstract=$(python3 -c "import sys; sys.path.insert(0,'print'); from prepare import VOLUMES; print(VOLUMES[$vol]['abstract'])")

  echo "==> Часть $vol — вёрстка PDF"
  # pandoc отдаёт .tex, дальше три прохода xelatex: первый собирает метки
  # указателя, xindy их сортирует по-русски, последние два подставляют
  # номера страниц и выравнивают оглавление
  ( cd print/build && pandoc "book${vol}.md" \
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
      --metadata volume="$vol" \
      --metadata volumetitle="$name" \
      --metadata abstract="$abstract" \
      -o "book${vol}.tex" )

  # xelatex возвращает ненулевой код и на безобидных предупреждениях,
  # поэтому не связываем проходы через && — успех проверяем по файлу
  ( cd print/build
    xelatex -interaction=nonstopmode "book${vol}.tex" > /dev/null 2>&1 || true
    texindy -L russian -C utf8 -M ../ruindex.xdy \
      -o "book${vol}.ind" "book${vol}.idx" > /dev/null 2>&1 || true
    xelatex -interaction=nonstopmode "book${vol}.tex" > /dev/null 2>&1 || true
    xelatex -interaction=nonstopmode "book${vol}.tex" > /dev/null 2>&1 || true
    if [ ! -f "book${vol}.pdf" ]; then
      echo "    ОШИБКА: PDF не собран, смотри print/build/book${vol}.log" >&2
      exit 1
    fi
    mv -f "book${vol}.pdf" "Разработка и применение ПО в физических исследованиях. Часть $vol.pdf" )

  local pages idx
  pages=$(grep -oE 'Output written on [^(]*\([0-9]+ pages' "print/build/book${vol}.log" \
          | grep -oE '[0-9]+ pages$' | grep -oE '[0-9]+' | tail -1)
  idx=$(grep -c '\\indexentry' "print/build/book${vol}.idx" 2>/dev/null || echo 0)
  echo "    готово: часть $vol — $pages стр., меток указателя: $idx"
  # схема ИПЦ для А4: страницы / 8 = уч.-изд. л.; х 0,93 = усл. печ. л.
  python3 - "$pages" <<'PY'
import sys
p = int(sys.argv[1] or 0)
if p:
    print(f"    для выходных данных: {p/8:g} уч.-изд. л., {p/8*0.93:.1f} усл. печ. л.")
PY
}

case "${1:-all}" in
  1) build_volume 1 "Теория" ;;
  2) build_volume 2 "Практика" ;;
  *) build_volume 1 "Теория"
     build_volume 2 "Практика" ;;
esac
