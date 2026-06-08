#!/usr/bin/env bash
# Trim whitespace margins from the four hunk-poly figure PDFs.
#
# Uses pdfcrop (lossless, vector-preserving — required for paper-grade
# figures; ImageMagick would rasterise and degrade quality). Reads every
# PDF under plots/ and writes a tightly-cropped copy under plots/trimmed/
# with the same filename.
#
# Usage:
#   ./trim_plots.sh                 # 0pt margin (tightest crop)
#   ./trim_plots.sh --margin 5      # 5pt all-around margin
#
# Requires: pdfcrop (TeX Live / MacTeX). Install on macOS:
#   brew install --cask mactex-no-gui          # or full mactex

set -euo pipefail
cd "$(dirname "$0")"

MARGIN=0
if [ "${1:-}" = "--margin" ]; then
  MARGIN="${2:?--margin requires a numeric argument (e.g. --margin 5)}"
fi

if ! command -v pdfcrop >/dev/null 2>&1; then
  echo "error: pdfcrop not found in PATH. Install TeX Live / MacTeX." >&2
  exit 1
fi

mkdir -p plots/trimmed

shopt -s nullglob
pdfs=(plots/*.pdf)
if [ ${#pdfs[@]} -eq 0 ]; then
  echo "error: no PDFs found in plots/. Run ./generate_all_plots.sh first." >&2
  exit 1
fi

for src in "${pdfs[@]}"; do
  name="$(basename "$src")"
  echo "==> $name (margin=${MARGIN}pt)"
  pdfcrop --margins "$MARGIN" "$src" "plots/trimmed/$name" >/dev/null
done

echo
echo "Trimmed PDFs (size comparison):"
for src in "${pdfs[@]}"; do
  name="$(basename "$src")"
  dst="plots/trimmed/$name"
  # stat is BSD on macOS (-f%z) and GNU on Linux (-c%s); fall back accordingly.
  src_size=$(stat -f%z "$src" 2>/dev/null || stat -c%s "$src")
  dst_size=$(stat -f%z "$dst" 2>/dev/null || stat -c%s "$dst")
  printf "  %-50s %8d -> %8d bytes\n" "$name" "$src_size" "$dst_size"
done
