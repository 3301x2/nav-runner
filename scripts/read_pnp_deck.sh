#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Read the PnP deck (PnPSpendJuly2026.pdf) locally and dump it into a form
# Prosper's assistant can consume through screenshots.
#
# What it does:
#   1. Confirms the PDF exists in ~/Downloads
#   2. Extracts every page to a JPG in ~/pnp_deck_pages/ (one per slide)
#   3. Extracts every page to raw text in ~/pnp_deck_pages/page_NN.txt
#   4. Prints a summary + tells Prosper which pics/pages to screenshot
#
# Dependencies auto-installed if missing:
#   - poppler (pdftoppm, pdftotext) via brew
#
# Read-only on the PDF, no BQ or GCS calls.
#
# Usage:
#   bash scripts/read_pnp_deck.sh [/path/to/deck.pdf]
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

PDF="${1:-$HOME/Downloads/PnPSpendJuly2026.pdf}"
OUT="$HOME/pnp_deck_pages"

echo
echo "════════════════════════════════════════════════════════════"
echo "  Read PnP deck locally, extract every slide as image + text"
echo "  PDF:    $PDF"
echo "  Output: $OUT/"
echo "════════════════════════════════════════════════════════════"

# ── 0. Ensure PDF exists ─────────────────────────────────────────────────
if [ ! -f "$PDF" ]; then
    echo
    echo "❌ PDF not found: $PDF"
    echo "   Try:  ls -la ~/Downloads/*.pdf"
    exit 1
fi

# ── 1. Ensure poppler is installed (pdftoppm + pdftotext) ───────────────
if ! command -v pdftoppm >/dev/null 2>&1 || ! command -v pdftotext >/dev/null 2>&1; then
    echo
    echo "── Installing poppler (needed for pdftoppm and pdftotext) ──"
    if command -v brew >/dev/null 2>&1; then
        brew install poppler
    else
        echo "❌ Homebrew not found. Install manually:  brew install poppler"
        exit 1
    fi
fi

# ── 2. Set up output directory ──────────────────────────────────────────
mkdir -p "$OUT"
rm -f "$OUT"/*.jpg "$OUT"/*.txt 2>/dev/null

# ── 3. Page count and metadata ──────────────────────────────────────────
echo
echo "── PDF metadata ──"
if command -v pdfinfo >/dev/null 2>&1; then
    pdfinfo "$PDF" | grep -iE 'pages|title|author|creation|modif|size' | head -6
fi
page_count=$(pdfinfo "$PDF" 2>/dev/null | grep -i "^Pages:" | awk '{print $2}')
echo
echo "  Total pages: ${page_count:-unknown}"

# ── 4. Extract every page as a JPG at readable resolution ──────────────
echo
echo "── Extracting every slide as JPG (~/pnp_deck_pages/page_NN.jpg) ──"
# 150 DPI is enough for a screenshot-quality image, keeps file sizes moderate
pdftoppm -jpeg -r 150 "$PDF" "$OUT/page" 2>&1 | tail -3
# Rename to zero-padded so ls sorts correctly
ls "$OUT" | grep -E '^page-[0-9]+\.jpg$' | while read -r f; do
    n=$(echo "$f" | sed -E 's/^page-([0-9]+)\.jpg$/\1/')
    nn=$(printf '%02d' "$n")
    mv "$OUT/$f" "$OUT/page_${nn}.jpg" 2>/dev/null || true
done

# ── 5. Extract raw text per page ────────────────────────────────────────
echo
echo "── Extracting text per page (~/pnp_deck_pages/page_NN.txt) ──"
for p in $(seq 1 "${page_count:-100}"); do
    nn=$(printf '%02d' "$p")
    pdftotext -layout -f "$p" -l "$p" "$PDF" "$OUT/page_${nn}.txt" 2>/dev/null || break
done

# ── 6. Summary ──────────────────────────────────────────────────────────
echo
echo "── Extraction summary ──"
n_jpg=$(ls "$OUT"/page_*.jpg 2>/dev/null | wc -l | tr -d ' ')
n_txt=$(ls "$OUT"/page_*.txt 2>/dev/null | wc -l | tr -d ' ')
total_size=$(du -sh "$OUT" 2>/dev/null | awk '{print $1}')
echo "  Extracted $n_jpg page images"
echo "  Extracted $n_txt page text files"
echo "  Total output size: $total_size"
echo
echo "── First 400 chars of each page (short titles reveal the deck spine) ──"
for f in "$OUT"/page_*.txt; do
    p=$(basename "$f" .txt | sed 's/page_//')
    echo
    echo "  ── page $p ──"
    head -c 400 "$f" | tr -s '[:space:]' ' ' | fold -sw 100 | sed 's/^/    /' | head -4
done

echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. Everything is at $OUT/"
echo
echo "  How to send them to the assistant:"
echo "    1. Look at ~/pnp_deck_pages/  and pick the pages that matter"
echo "       (usually slides 9-13 based on Marina's brief, plus any"
echo "        slide with turquoise segment highlights)"
echo "    2. Screenshot each page (Cmd+Shift+4, then click the JPG"
echo "       in Preview) or drag the JPGs into Downloads"
echo "    3. Say 'check latest pics' and the assistant reads them"
echo
echo "  Priority slides to send first: 9, 10, 11, 12, 13"
echo "════════════════════════════════════════════════════════════"
