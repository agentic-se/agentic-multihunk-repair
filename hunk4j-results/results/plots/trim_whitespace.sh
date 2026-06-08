#!/bin/bash
mkdir -p final_trimmed
for pdf in *.pdf; do
    [ -f "$pdf" ] || continue
    convert -density 300 -trim +repage -quality 100 "$pdf" "final_trimmed/${pdf%.pdf}_trimmed.pdf"
    echo "Trimmed: $pdf"
done
