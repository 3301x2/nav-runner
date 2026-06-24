#!/usr/bin/env python3
"""
Builds the audience-segment-breakdown HTML for Adidas + Superbalist.

Produces a single self-contained file (audience_segment_breakdown.html) with
two tables matching Leandra's Asana layout exactly:
  - 9 rows (Entry Wallet → RMB)
  - 3 columns (Lead Load ETB, Lead Load NTB, Open Market ETB)

Decoder (Pierre WhatsApp, 24 Jun 2026):
  EL*  → Entry Wallet
  EU*  → Entry Banking
  GL*  → Middle Market
  PB*  → Emerging Affluent
  PC*  → Affluent
  PW0  → Wealth (per Pierre, aggregates PW0 + PWU + PWH)
  PWU  → Ultra High Net Worth
  PWH  → High Net Worth

Assumptions (per Pierre):
  - All FNB cardholders → ETB column (no NTB / Open Market in our data)
  - Signet & RMB rows cannot be separated from Wealth — shown as n/a

Usage:
  python3 scripts/build_audience_grids.py [sandbox|production]
"""
from __future__ import annotations
import html as _h
import sys
from datetime import datetime

from google.cloud import bigquery


# ── Env / project ─────────────────────────────────────────────────────────
ENV = sys.argv[1] if len(sys.argv) > 1 else 'sandbox'
PROJECT_MAP = {
    'sandbox': 'fmn-sandbox', 'dev': 'fmn-sandbox', 'sb': 'fmn-sandbox',
    'production': 'fmn-production', 'prod': 'fmn-production', 'prd': 'fmn-production',
}
if ENV not in PROJECT_MAP:
    sys.exit(f'Usage: python3 {sys.argv[0]} [sandbox|production]')
PROJECT = PROJECT_MAP[ENV]
print(f'Project: {PROJECT}')

bq = bigquery.Client(project=PROJECT)


# ── Grid SQL (parametrised per client) ────────────────────────────────────
GRID_SQL = """
WITH client_custs AS (
    SELECT DISTINCT UNIQUE_ID
    FROM `{project}.analytics.int_customer_category_spend`
    WHERE UPPER(DESTINATION) LIKE '%{brand}%'
),
decoded AS (
    SELECT
        CASE
            WHEN c.income_segment LIKE 'EL%' THEN 'Entry Wallet'
            WHEN c.income_segment LIKE 'EU%' THEN 'Entry Banking'
            WHEN c.income_segment LIKE 'GL%' THEN 'Middle Market'
            WHEN c.income_segment LIKE 'PB%' THEN 'Emerging Affluent'
            WHEN c.income_segment LIKE 'PC%' THEN 'Affluent'
            WHEN c.income_segment IN ('PW0','PWU','PWH') THEN 'Wealth'
            ELSE 'Unknown'
        END AS sub_segment
    FROM client_custs s
    LEFT JOIN `{project}.staging.stg_customers` c USING (UNIQUE_ID)
)
SELECT sub_segment, COUNT(*) AS customers
FROM decoded
GROUP BY sub_segment
"""


def fetch_grid(brand: str) -> dict[str, int]:
    print(f'  Querying {brand}...')
    sql = GRID_SQL.format(project=PROJECT, brand=brand.upper())
    rows = bq.query(sql).result()
    return {r['sub_segment']: int(r['customers']) for r in rows}


# Fetch both
print('Fetching Adidas grid...')
adidas = fetch_grid('ADIDAS')
print(f'  → {sum(adidas.values()):,} total customers')

print('Fetching Superbalist grid...')
superbalist = fetch_grid('SUPERBALIST')
print(f'  → {sum(superbalist.values()):,} total customers')


# ── Build the 9-row × 3-col grid (Leandra's exact layout) ─────────────────
SUB_SEGMENTS = [
    'Entry Wallet',
    'Entry Banking',
    'Middle Market',
    'Emerging Affluent',
    'Affluent',
    'Wealth',
    'UHNW',
    'Signet',
    'RMB',
]


def fmt(n) -> str:
    if n is None or n == 0:
        return ''
    return f'{n:,}'


def grid_rows(data: dict[str, int]) -> str:
    """Render 9 rows × 3 cols matching Leandra's layout exactly."""
    out = ''
    for seg in SUB_SEGMENTS:
        if seg in ('UHNW', 'Signet', 'RMB'):
            # Per Pierre: Signet & RMB included in Wealth, can't be split.
            # UHNW we DO have (PWU) but Pierre said treat Wealth as one combined number.
            etb_cell = '<span class="na">included in Wealth</span>'
        else:
            etb_cell = fmt(data.get(seg, 0))
        out += (
            f'<tr><td class="seg">{_h.escape(seg)}</td>'
            f'<td class="vol">{etb_cell}</td>'
            f'<td class="vol"></td>'
            f'<td class="vol"></td></tr>'
        )
    return out


# ── Build HTML ────────────────────────────────────────────────────────────
adidas_html = grid_rows(adidas)
superbalist_html = grid_rows(superbalist)

now = datetime.now().strftime('%d %B %Y')

html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Audience Segment Breakdown — Adidas & Superbalist</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Inter',sans-serif; background:#f8fafc; color:#0f172a; padding:32px 24px; line-height:1.5; }}
.container {{ max-width:900px; margin:0 auto; }}
h1 {{ font-size:1.6rem; font-weight:700; margin-bottom:6px; }}
.meta {{ color:#64748b; font-size:.85rem; margin-bottom:24px; }}
.callout {{ background:#fef9c3; border-left:4px solid #ca8a04; border-radius:0 8px 8px 0; padding:14px 18px; margin:16px 0 24px; font-size:.88rem; color:#713f12; line-height:1.55; }}
.callout strong {{ color:#451a03; }}
h2 {{ font-size:1.2rem; font-weight:600; margin:32px 0 12px; color:#1e3a5f; }}
table {{ width:100%; border-collapse:collapse; margin-bottom:16px; border:1px solid #e2e8f0; }}
thead th {{ background:#0f172a; color:#fff; padding:10px 14px; text-align:left; font-size:.78rem; font-weight:600; text-transform:uppercase; letter-spacing:.04em; }}
thead th.vol-h {{ text-align:right; }}
td {{ padding:9px 14px; border-bottom:1px solid #f1f5f9; font-size:.9rem; }}
td.seg {{ font-weight:500; color:#0f172a; }}
td.vol {{ text-align:right; font-variant-numeric:tabular-nums; color:#334155; }}
.na {{ color:#94a3b8; font-style:italic; font-size:.78rem; }}
tr:hover td {{ background:#fafafa; }}
.totals {{ background:#f1f5f9; font-weight:600; }}
.totals td {{ border-bottom:none; }}
.footnote {{ font-size:.78rem; color:#64748b; margin-top:8px; line-height:1.5; }}
</style>
</head><body>
<div class="container">

<h1>Audience Segment Breakdown</h1>
<div class="meta">Source: {PROJECT} · Generated {now}</div>

<div class="callout">
<strong>Caveats (per Pierre, 24 Jun):</strong>
<ul style="margin:6px 0 0 18px">
<li>All volumes sit under <strong>Lead Load (ETB)</strong> — every customer in our data is FNB-banked by definition, so <strong>Lead Load (NTB)</strong> and <strong>Open Market (ETB)</strong> columns are empty.</li>
<li><strong>Wealth</strong> row combines PW0 + PWU + PWH per Pierre's instruction (treated as one combined wealth base).</li>
<li><strong>UHNW</strong>, <strong>Signet</strong>, <strong>RMB</strong>: cannot be separated from Wealth in the current dataset — shown as <em>included in Wealth above</em>.</li>
</ul>
</div>

<h2>Adidas — Audience Segment Breakdown</h2>
<table>
<thead><tr>
<th>Sub-Segments</th>
<th class="vol-h">Lead Load Volumes (ETB)</th>
<th class="vol-h">Lead Load Volumes (NTB)</th>
<th class="vol-h">Open Market Volumes (ETB)</th>
</tr></thead>
<tbody>
{adidas_html}
<tr class="totals"><td>Total</td><td class="vol">{fmt(sum(v for k,v in adidas.items() if k != 'Unknown'))}</td><td class="vol"></td><td class="vol"></td></tr>
</tbody>
</table>
<div class="footnote">Based on customers with at least one transaction at an Adidas-branded merchant in the last 12 months.</div>

<h2>Superbalist — Audience Segment Breakdown</h2>
<table>
<thead><tr>
<th>Sub-Segments</th>
<th class="vol-h">Lead Load Volumes (ETB)</th>
<th class="vol-h">Lead Load Volumes (NTB)</th>
<th class="vol-h">Open Market Volumes (ETB)</th>
</tr></thead>
<tbody>
{superbalist_html}
<tr class="totals"><td>Total</td><td class="vol">{fmt(sum(v for k,v in superbalist.items() if k != 'Unknown'))}</td><td class="vol"></td><td class="vol"></td></tr>
</tbody>
</table>
<div class="footnote">Based on customers with at least one transaction at Superbalist in the last 12 months.</div>

</div>
</body></html>
"""

OUT = 'audience_segment_breakdown.html'
with open(OUT, 'w') as f:
    f.write(html)

print()
print(f'Wrote: {OUT}')
print('Open in a browser and screenshot for Asana.')
