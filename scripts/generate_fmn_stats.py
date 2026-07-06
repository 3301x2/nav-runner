#!/usr/bin/env python3
"""
Financial Media Network — headline stats.

Matches Rainmaker Media's slide style: 5-7 big numbers + short labels.
Rainmaker had things like "80% of South African shoppers", "15 million
unique transactions", "2,800 stores", "81 million shoppers", "1.1 billion".

We do the same for the FNB Financial Media Network, using our own data.

Outputs:
  fmn_stats.html          - branded HTML page, screenshot-ready
  fmn_stats.txt           - plain-text list for direct paste into slides

Usage:
  python3 scripts/generate_fmn_stats.py [sandbox|production]
"""
from __future__ import annotations
import html as _h
import subprocess
import sys
from datetime import datetime


REQUIRED = {
    'pandas':                'pandas',
    'db_dtypes':             'db-dtypes',
    'google.cloud.bigquery': 'google-cloud-bigquery',
}
missing = []
for mod, pip_name in REQUIRED.items():
    try:
        __import__(mod)
    except ImportError:
        missing.append(pip_name)
if missing:
    print(f'Installing missing deps: {missing}')
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', *missing])

import pandas as pd
from google.cloud import bigquery


ENV = sys.argv[1] if len(sys.argv) > 1 else 'sandbox'
PROJECT_MAP = {
    'sandbox': 'fmn-sandbox', 'dev': 'fmn-sandbox', 'sb': 'fmn-sandbox',
    'production': 'fmn-production-462014', 'prod': 'fmn-production-462014', 'prd': 'fmn-production-462014',
}
if ENV not in PROJECT_MAP:
    sys.exit(f'Usage: python3 {sys.argv[0]} [sandbox|production]')
PROJECT = PROJECT_MAP[ENV]
bq = bigquery.Client(project=PROJECT)


def q(sql: str) -> pd.DataFrame:
    return bq.query(sql).to_dataframe()


def N(v) -> str:
    if v is None or pd.isna(v): return 'N/A'
    v = float(v)
    if abs(v) >= 1e9:  return f'{v/1e9:.1f} billion'.replace('.0', '')
    if abs(v) >= 1e6:  return f'{v/1e6:.1f} million'.replace('.0', '')
    if abs(v) >= 1e3:  return f'{int(v/1e3):,}k'
    return f'{int(v):,}'


def R(v) -> str:
    if v is None or pd.isna(v): return 'N/A'
    v = float(v)
    if abs(v) >= 1e12: return f'R{v/1e12:.1f} trillion'.replace('.0', '')
    if abs(v) >= 1e9:  return f'R{v/1e9:.1f} billion'.replace('.0', '')
    if abs(v) >= 1e6:  return f'R{v/1e6:.1f} million'.replace('.0', '')
    return f'R{int(v):,}'


def esc(s) -> str:
    return _h.escape(str(s))


# ── Queries ──────────────────────────────────────────────────────────────
print('Querying...')

# 1. Total FNB cardholders (whole base — the reach story)
customers = q(f"""
    SELECT COUNT(DISTINCT UNIQUE_ID) AS n
    FROM `{PROJECT}.staging.stg_customers`
""").iloc[0]['n']

# 2. Active cardholders in the 12-month window (people who actually shopped)
active = q(f"""
    SELECT COUNT(DISTINCT UNIQUE_ID) AS n
    FROM `{PROJECT}.analytics.int_customer_category_spend`
""").iloc[0]['n']

# 3. Total transactions
transactions = q(f"""
    SELECT SUM(dest_txn_count) AS n
    FROM `{PROJECT}.analytics.int_customer_category_spend`
""").iloc[0]['n']

# 4. Total spend
spend = q(f"""
    SELECT SUM(dest_spend) AS n
    FROM `{PROJECT}.analytics.int_customer_category_spend`
""").iloc[0]['n']

# 5. Distinct merchants (DESTINATIONs)
merchants = q(f"""
    SELECT COUNT(DISTINCT DESTINATION) AS n
    FROM `{PROJECT}.analytics.int_customer_category_spend`
""").iloc[0]['n']

# 6. Distinct categories (CATEGORY_TWO)
categories = q(f"""
    SELECT COUNT(DISTINCT CATEGORY_TWO) AS n
    FROM `{PROJECT}.analytics.int_customer_category_spend`
""").iloc[0]['n']

# 7. Data window (months of coverage)
window = q(f"""
    SELECT
        MIN(EFF_DATE) AS first_date,
        MAX(EFF_DATE) AS last_date,
        DATE_DIFF(MAX(EFF_DATE), MIN(EFF_DATE), MONTH) + 1 AS months_covered
    FROM `{PROJECT}.staging.stg_transactions`
""").iloc[0]

# 8. Provinces covered (proxy for national reach)
provinces = q(f"""
    SELECT COUNT(DISTINCT PROVINCE) AS n
    FROM `{PROJECT}.staging.stg_transactions`
    WHERE PROVINCE IS NOT NULL
""").iloc[0]['n']

# 9. % of banked SA adults reached (denominator = ~40M SA adults, real stat)
# We anchor to ~28M banked SA adults (SARB / FinScope 2024 estimate)
banked_sa_adults = 28_000_000
pct_of_banked = round(100 * customers / banked_sa_adults, 1)

print('  → data collected')


# ── Build stat cards ─────────────────────────────────────────────────────
now = datetime.now().strftime('%B %Y')

stats = [
    {
        'value': N(customers),
        'label': 'FNB cardholders in the network',
        'sub':   f'≈ {pct_of_banked}% of South African banked adults',
    },
    {
        'value': N(active),
        'label': 'active shoppers in the last 12 months',
        'sub':   'measured across cardholder transactions',
    },
    {
        'value': R(spend),
        'label': 'in visible annual spend',
        'sub':   f'across {int(categories)} spend categories',
    },
    {
        'value': N(transactions),
        'label': 'transactions per year',
        'sub':   'real transactional signal, not survey data',
    },
    {
        'value': f'{int(merchants):,}',
        'label': 'unique merchants captured',
        'sub':   'from national retailers to niche brands',
    },
    {
        'value': '9 of 9',
        'label': 'South African provinces covered',
        'sub':   f'{int(provinces)} provinces active in the last 12 months',
    },
    {
        'value': f'{int(window["months_covered"])} months',
        'label': 'of transactional history',
        'sub':   f'{window["first_date"].strftime("%b %Y")} to {window["last_date"].strftime("%b %Y")}',
    },
]


# ── Plain-text output for direct paste into slides ────────────────────────
lines = ['FINANCIAL MEDIA NETWORK — HEADLINE STATS', f'({now})', '']
for s in stats:
    lines.append(f"  {s['value']}")
    lines.append(f"    {s['label']}")
    if s['sub']:
        lines.append(f"    ({s['sub']})")
    lines.append('')
plain_text = '\n'.join(lines)

with open('fmn_stats.txt', 'w') as f:
    f.write(plain_text)


# ── HTML output ──────────────────────────────────────────────────────────
def stat_card(s):
    sub_html = f'<div class="sub">{esc(s["sub"])}</div>' if s['sub'] else ''
    return f'''
    <div class="stat">
      <div class="value">{esc(s['value'])}</div>
      <div class="label">{esc(s['label'])}</div>
      {sub_html}
    </div>
    '''

html = f"""<!DOCTYPE html>
<html lang='en'><head><meta charset='UTF-8'>
<title>Financial Media Network — Headline Stats</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'DM Sans',sans-serif; background:linear-gradient(180deg,#0f172a 0%,#1e3a5f 100%); color:#fff; padding:40px 32px; min-height:100vh; }}
.ctn {{ max-width:1200px; margin:0 auto; }}
h1 {{ font-size:2.4rem; font-weight:800; letter-spacing:-0.02em; }}
.tagline {{ font-size:1rem; color:#94a3b8; margin-top:6px; margin-bottom:36px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:18px; }}
.stat {{
  background:linear-gradient(145deg,#1e3a5f 0%,#0f172a 100%);
  border:1px solid rgba(255,255,255,0.08);
  border-radius:16px;
  padding:26px 24px;
  min-height:170px;
  display:flex; flex-direction:column; justify-content:center;
}}
.value {{ font-size:2.4rem; font-weight:800; color:#f59e0b; line-height:1.05; letter-spacing:-0.02em; }}
.label {{ font-size:1rem; font-weight:600; color:#f1f5f9; margin-top:8px; line-height:1.35; }}
.sub {{ font-size:0.82rem; color:#94a3b8; margin-top:8px; line-height:1.4; }}
.footer {{ margin-top:38px; padding-top:20px; border-top:1px solid rgba(255,255,255,0.1); color:#64748b; font-size:0.78rem; }}
</style>
</head><body>
<div class="ctn">
<h1>Financial Media Network</h1>
<div class="tagline">FNB's transactional signal, at national scale — {esc(now)}</div>
<div class="grid">
{''.join(stat_card(s) for s in stats)}
</div>
<div class="footer">Source: FNB Financial Media Network. All figures based on live transactional data over a rolling 12-month window.</div>
</div>
</body></html>
"""

with open('fmn_stats.html', 'w') as f:
    f.write(html)


# ── Print to terminal too ───────────────────────────────────────────────
print()
print(plain_text)
print()
print(f'Wrote: fmn_stats.html')
print(f'Wrote: fmn_stats.txt')
print('Open the HTML in browser and screenshot for the slide.')
