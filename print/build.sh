#!/usr/bin/env bash
# Собирает печатный оригинал-макет пособия (А5, требования ИПЦ НГУ).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Подготовка markdown"
python3 print/prepare.py

echo "==> Вёрстка PDF (xelatex через pandoc)"
cd print/build
pandoc book.md \
  --from=markdown+pipe_tables+backtick_code_blocks+tex_math_dollars+raw_tex+autolink_bare_uris+lists_without_preceding_blankline \
  --to=pdf \
  --pdf-engine=xelatex \
  --template=../template.tex \
  --top-level-division=chapter \
  --toc --toc-depth=2 \
  --number-sections \
  --highlight-style=tango \
  --resource-path=.:img \
  --metadata title="Разработка и применение программного обеспечения в физических исследованиях" \
  --metadata author="В. В. Федоров" \
  --metadata lang=ru \
  -o "Разработка и применение ПО в физических исследованиях.pdf"

echo "==> Готово: print/build/Разработка и применение ПО в физических исследованиях.pdf"
