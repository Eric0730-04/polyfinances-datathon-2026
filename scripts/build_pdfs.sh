#!/usr/bin/env bash
# Build the submission PDFs from the Markdown sources in docs/.
# Needs pandoc and xelatex (TeX Live / MacTeX). Run from the repo root.
set -euo pipefail
cd "$(dirname "$0")/../docs"
OPTS=(--pdf-engine=xelatex -f markdown+lists_without_preceding_blankline
      -V geometry:margin=0.7in -V fontsize=10pt
      -V mainfont="DejaVu Sans" -V monofont="DejaVu Sans Mono")
pandoc one_pager.md -o one_pager.pdf "${OPTS[@]}" -V pagestyle=empty -V geometry:margin=0.6in
pandoc technical_documentation.md -o technical_documentation.pdf "${OPTS[@]}" \
  --lua-filter=../scripts/pdf_filter.lua
echo "Built docs/one_pager.pdf and docs/technical_documentation.pdf"
