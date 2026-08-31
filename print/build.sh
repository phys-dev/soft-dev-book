#!/usr/bin/env bash
# Собирает оригинал-макет пособия (А5, требования ИПЦ НГУ).
# Без аргументов собирает обе части; можно указать номер: build.sh 1
set -euo pipefail
cd "$(dirname "$0")/.."

TITLE="Разработка и применение программного обеспечения в физических исследованиях"
AUTHOR="В. В. Федоров"

build_volume() {
  local vol="$1" name="$2" abstract="$3"
  echo "==> Часть $vol. $name — подготовка markdown"
  python3 print/prepare.py "$vol"

  echo "==> Часть $vol — вёрстка PDF"
  # pandoc отдаёт .tex, дальше три прохода xelatex: первый собирает
  # метки указателя, xindy их сортирует по-русски, последние два
  # подставляют номера страниц и выравнивают оглавление
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

  local n
  n=$(grep -c '\\indexentry' "print/build/book${vol}.idx" 2>/dev/null || echo 0)
  echo "    готово: print/build/Разработка и применение ПО в физических исследованиях. Часть $vol.pdf (меток указателя: $n)"
}

A1="Первая часть пособия вводит в рабочую среду и базовые знания, без которых научная разработка превращается в кустарщину: операционная система GNU/Linux, алгоритмы и структуры данных, понятия сходимости и устойчивости численных схем, устройство языка Python и инженерные практики разработки — от жизненного цикла программы до баз данных."
A2="Вторая часть пособия посвящена работе с данными физического эксперимента и производительности программ: обработка и визуализация массивов, машинное обучение и нейронные сети, профилирование, многопоточность, асинхронность и вычисления на графических ускорителях. Завершают книгу разбор реальных кодов, применяемых в институтах СО РАН, и задания для самостоятельной работы."

case "${1:-all}" in
  1) build_volume 1 "Инструменты и основы" "$A1" ;;
  2) build_volume 2 "Данные, ускорение и практика" "$A2" ;;
  *) build_volume 1 "Инструменты и основы" "$A1"
     build_volume 2 "Данные, ускорение и практика" "$A2" ;;
esac
