#!/usr/bin/env python3
"""
Jetour — client-facing pitch. PROXY MODE.

Jetour is not in FNB card data at meaningful scale — the brand entered SA
in Sept 2024 with 40 dealerships, and vehicle purchases don't hit debit
cards typically.

This pitch shows three PROXY AUDIENCES side by side, with an explainer
at the top so the salesperson can pick which angle fits their client
conversation:

  A — Direct Chinese-brand shoppers
      (Mahindra + GWM DESTINATIONs — closest brand substitutes)
      SMALL but sharp — for brand-vs-brand pitches

  B — Value car audience
      (Suzuki + Mahindra + GWM + Toyota entry + Hyundai + Kia)
      MEDIUM — the affordable-vehicle buyer cohort, best all-round story

  C — All vehicle-active FNB customers
      (Vehicle Maintenance & Dealerships category)
      LARGEST — top-of-funnel awareness story

Default demographics / geo / activation views use option B.
"""
from __future__ import annotations
import html as _h
import json
import subprocess
import sys
import warnings
warnings.filterwarnings('ignore', message='.*BigQuery Storage.*')
from datetime import datetime


REQUIRED = {
    'pandas':                'pandas',
    'db_dtypes':             'db-dtypes',
    'google.cloud.bigquery': 'google-cloud-bigquery',
  'google.cloud.bigquery_storage': 'google-cloud-bigquery-storage',
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


def q(sql): return bq.query(sql).to_dataframe()

def R(v):
    if v is None or pd.isna(v): return 'N/A'
    v = float(v)
    if abs(v) >= 1e9:  return f'R{v/1e9:.2f}B'
    if abs(v) >= 1e6:  return f'R{v/1e6:.1f}M'
    if abs(v) >= 1e3:  return f'R{v/1e3:.0f}k'
    return f'R{v:,.0f}'

def R_exact(v):
    if v is None or pd.isna(v): return 'N/A'
    return f'R{float(v):,.0f}'

def N(v):
    if v is None or pd.isna(v): return 'N/A'
    return f'{int(v):,}'

def esc(s): return _h.escape(str(s))


# ── Proxy audience filters ───────────────────────────────────────────────
# A: Direct Chinese-brand competitors
FILTER_A = "UPPER(DESTINATION) IN ('MAHINDRA','GWM')"

# B: Value car audience (Suzuki + Chinese + entry-level Japanese)
FILTER_B = """
    UPPER(DESTINATION) IN ('SUZUKI','MAHINDRA','GWM','TOYOTA','HYUNDAI','KIA')
"""

# C: All vehicle-active customers (biggest audience)
FILTER_C = "CATEGORY_TWO = 'Vehicle Maintenance & Dealerships'"


# ── Queries ──────────────────────────────────────────────────────────────
print('Querying...')

def hero_for(filter_sql):
    return q(f"""
        SELECT
            COUNT(DISTINCT UNIQUE_ID)                                        AS customers,
            SUM(dest_txn_count)                                              AS transactions,
            ROUND(SUM(dest_spend), 0)                                        AS total_spend,
            ROUND(SUM(dest_spend) / NULLIF(SUM(dest_txn_count), 0), 2)       AS avg_txn_value,
            ROUND(SUM(dest_spend) / NULLIF(COUNT(DISTINCT UNIQUE_ID), 0), 0) AS spend_per_customer
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE {filter_sql}
    """).iloc[0]

hero_a = hero_for(FILTER_A)
hero_b = hero_for(FILTER_B)
hero_c = hero_for(FILTER_C)

print(f'  A (Chinese brand):   {int(hero_a["customers"]):>10,} customers · {R(hero_a["total_spend"])}')
print(f'  B (Value car):       {int(hero_b["customers"]):>10,} customers · {R(hero_b["total_spend"])}')
print(f'  C (All vehicle):     {int(hero_c["customers"]):>10,} customers · {R(hero_c["total_spend"])}')

# All downstream (demographics, geo, activation, etc.) use option B as the default
demo = q(f"""
    WITH custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE {FILTER_B}
    )
    SELECT
        COUNT(*)                                                                 AS customers,
        ROUND(AVG(c.age), 1)                                                     AS avg_age,
        COUNT(DISTINCT CASE WHEN c.gender_label='Male'   THEN c.UNIQUE_ID END)   AS male,
        COUNT(DISTINCT CASE WHEN c.gender_label='Female' THEN c.UNIQUE_ID END)   AS female
    FROM custs f JOIN `{PROJECT}.staging.stg_customers` c USING (UNIQUE_ID)
""").iloc[0]

income_gender = q(f"""
    WITH custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE {FILTER_B}
    )
    SELECT c.income_group AS band,
           COUNT(DISTINCT CASE WHEN c.gender_label='Male' THEN c.UNIQUE_ID END) AS male,
           COUNT(DISTINCT CASE WHEN c.gender_label='Female' THEN c.UNIQUE_ID END) AS female
    FROM custs f JOIN `{PROJECT}.staging.stg_customers` c USING (UNIQUE_ID)
    WHERE c.income_group IS NOT NULL AND c.income_group <> 'Unknown'
    GROUP BY c.income_group
    ORDER BY CASE c.income_group
      WHEN 'R0-R5.5k' THEN 1 WHEN 'R5.5k-R13.5k' THEN 2 WHEN 'R13.5k-R23.5k' THEN 3
      WHEN 'R23.5k-R32.5k' THEN 4 WHEN 'R32.5k-R56k' THEN 5 WHEN 'R56k+' THEN 6 ELSE 99 END
""").to_dict('records')

age_gender = q(f"""
    WITH custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE {FILTER_B}
    )
    SELECT c.age_group AS band,
           COUNT(DISTINCT CASE WHEN c.gender_label='Male' THEN c.UNIQUE_ID END) AS male,
           COUNT(DISTINCT CASE WHEN c.gender_label='Female' THEN c.UNIQUE_ID END) AS female
    FROM custs f JOIN `{PROJECT}.staging.stg_customers` c USING (UNIQUE_ID)
    WHERE c.age_group IS NOT NULL AND c.age_group <> 'Unknown'
    GROUP BY c.age_group
    ORDER BY CASE c.age_group
      WHEN '18-25' THEN 1 WHEN '26-35' THEN 2 WHEN '36-45' THEN 3
      WHEN '46-60' THEN 4 WHEN '60+' THEN 5 ELSE 99 END
""").to_dict('records')

geo = q(f"""
    WITH custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE {FILTER_B}
    )
    SELECT t.PROVINCE AS province,
           COUNT(DISTINCT t.UNIQUE_ID) AS customers,
           ROUND(SUM(t.trns_amt), 0)   AS spend
    FROM custs f JOIN `{PROJECT}.staging.stg_transactions` t USING (UNIQUE_ID)
    WHERE UPPER(t.DESTINATION) IN ('SUZUKI','MAHINDRA','GWM','TOYOTA','HYUNDAI','KIA')
      AND t.PROVINCE IS NOT NULL
    GROUP BY t.PROVINCE
    ORDER BY spend DESC LIMIT 9
""").to_dict('records')

segments = q(f"""
    WITH custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE {FILTER_B}
    )
    SELECT co.segment_name AS segment,
           COUNT(*) AS customers,
           ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
    FROM custs f JOIN `{PROJECT}.marts.mart_cluster_output` co USING (UNIQUE_ID)
    GROUP BY co.segment_name ORDER BY customers DESC
""").to_dict('records')

segment_spend = q(f"""
    WITH activity AS (
        SELECT cs.UNIQUE_ID, SUM(cs.dest_spend) AS client_spend
        FROM `{PROJECT}.analytics.int_customer_category_spend` cs
        WHERE UPPER(cs.DESTINATION) IN ('SUZUKI','MAHINDRA','GWM','TOYOTA','HYUNDAI','KIA')
        GROUP BY cs.UNIQUE_ID
    )
    SELECT co.segment_name AS segment,
           COUNT(*) AS customers,
           ROUND(SUM(a.client_spend), 0) AS client_annual_spend
    FROM activity a JOIN `{PROJECT}.marts.mart_cluster_output` co USING (UNIQUE_ID)
    GROUP BY co.segment_name
""").to_dict('records')

cross_shop = q(f"""
    WITH custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE {FILTER_B}
    )
    SELECT cs.CATEGORY_TWO AS category,
           COUNT(DISTINCT cs.UNIQUE_ID) AS shoppers,
           ROUND(SUM(cs.dest_spend), 0) AS spend
    FROM custs f JOIN `{PROJECT}.analytics.int_customer_category_spend` cs USING (UNIQUE_ID)
    WHERE cs.CATEGORY_TWO <> 'Vehicle Maintenance & Dealerships'
    GROUP BY cs.CATEGORY_TWO
    ORDER BY shoppers DESC LIMIT 8
""").to_dict('records')

print('  → data collected')


# ── Bundle for Chart.js ──────────────────────────────────────────────────
data_obj = {
    'income_gender': [{'band': r['band'], 'male': int(r['male']), 'female': int(r['female'])} for r in income_gender],
    'age_gender':    [{'band': r['band'], 'male': int(r['male']), 'female': int(r['female'])} for r in age_gender],
    'geo':           [{'province': r['province'], 'customers': int(r['customers']), 'spend': float(r['spend'])} for r in geo],
    'segments':      [{'name': s['segment'], 'customers': int(s['customers']), 'pct': float(s['pct'])} for s in segments],
}

now = datetime.now().strftime('%d %B %Y')


def kpi(label, value, sub=''):
    sub_html = f'<div class="s">{esc(sub)}</div>' if sub else ''
    return f'<div class="card"><div class="l">{esc(label)}</div><div class="v">{esc(value)}</div>{sub_html}</div>'


total_gender = int(demo['male']) + int(demo['female'])
demo_row = ''.join([
    kpi('Female', f'{round(100*demo["female"]/total_gender,1)}%', f'{N(demo["female"])} customers'),
    kpi('Male', f'{round(100*demo["male"]/total_gender,1)}%', f'{N(demo["male"])} customers'),
    kpi('Avg age', f'{demo["avg_age"]}', 'years'),
])

top_2 = round(sum(s['pct'] for s in segments[:2]), 1) if len(segments) >= 2 else 0
ss = {s['segment']: s for s in segment_spend}
def sz(n): r = next((s for s in segments if s['segment']==n), None); return int(r['customers']) if r else 0
def sp(n): r = ss.get(n); return int(r['client_annual_spend']) if r else 0
protect = sz('Champions') + sz('Loyal High Value')
grow = sz('Steady Mid-Tier')
reeng = sz('At Risk') + sz('Dormant')
protect_s = sp('Champions') + sp('Loyal High Value')
grow_s = sp('Steady Mid-Tier')
reeng_s = sp('At Risk') + sp('Dormant')

cross_rows = ''.join(
    f'<tr><td>{esc(r["category"])}</td><td>{N(r["shoppers"])}</td><td>{R(r["spend"])}</td></tr>'
    for r in cross_shop
)


# Audience-option cards for the top of the deck
option_cards = f"""
<div class='option-grid'>
  <div class='option-card option-a'>
    <div class='option-badge'>OPTION A · SHARP</div>
    <h3>Direct Chinese-brand shoppers</h3>
    <div class='option-size'>{N(hero_a['customers'])}</div>
    <div class='option-spend'>{R(hero_a['total_spend'])} annual spend</div>
    <div class='option-desc'>Mahindra + GWM shoppers — the closest brand substitutes for Jetour today.</div>
    <div class='option-when'><b>Pick this when:</b> pitching Jetour as "the next Chinese SUV brand", brand-vs-brand comparison, or narrowly targeted digital.</div>
  </div>
  <div class='option-card option-b'>
    <div class='option-badge'>OPTION B · RECOMMENDED</div>
    <h3>Value car audience</h3>
    <div class='option-size'>{N(hero_b['customers'])}</div>
    <div class='option-spend'>{R(hero_b['total_spend'])} annual spend</div>
    <div class='option-desc'>Suzuki + Mahindra + GWM + Toyota + Hyundai + Kia shoppers — the affordable, practical-vehicle cohort. Best all-round Jetour story.</div>
    <div class='option-when'><b>Pick this when:</b> pitching Jetour on value + tech + affordability, competing across the "smart practical buyer" segment. Default view for demographics below.</div>
  </div>
  <div class='option-card option-c'>
    <div class='option-badge'>OPTION C · BROAD</div>
    <h3>All vehicle-active FNB customers</h3>
    <div class='option-size'>{N(hero_c['customers'])}</div>
    <div class='option-spend'>{R(hero_c['total_spend'])} annual spend</div>
    <div class='option-desc'>Every FNB cardholder with dealership + service activity — the whole vehicle-active audience.</div>
    <div class='option-when'><b>Pick this when:</b> top-of-funnel awareness campaigns, brand launch, maximum reach at the cost of precision.</div>
  </div>
</div>
"""


CSS = """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#f8fafc;color:#1a202c}
#hdr{background:linear-gradient(135deg,#0f172a,#a67c00);color:#fff;padding:28px 32px}
#hdr h1{font-size:1.9rem;font-weight:700}
#hdr p{opacity:.9;font-size:1rem;margin-top:6px}
#hdr .meta{font-size:.78rem;opacity:.6;margin-top:14px}
.ctn{max-width:1200px;margin:0 auto;padding:24px}
.sec{background:#fff;border-radius:14px;padding:26px 30px;margin:18px 0;border:1px solid #f1f5f9;box-shadow:0 1px 4px rgba(0,0,0,.04)}
.sec h2{font-size:1.35rem;font-weight:700;color:#0f172a;margin-bottom:6px}
.sec .sub{color:#64748b;font-size:.92rem;margin-bottom:18px;line-height:1.5}
.proxy-notice{background:#fef3c7;border:2px solid #f59e0b;border-radius:12px;padding:20px 24px;margin:0 0 18px}
.proxy-notice h3{color:#78350f;font-size:1.15rem;font-weight:700;margin-bottom:6px}
.proxy-notice p{color:#78350f;font-size:.95rem;line-height:1.55}
.option-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:14px}
@media(max-width:900px){.option-grid{grid-template-columns:1fr}}
.option-card{background:#fff;border-radius:12px;padding:20px 22px;border:2px solid #f1f5f9;position:relative}
.option-card h3{font-size:1.1rem;font-weight:700;color:#0f172a;margin:8px 0 4px}
.option-badge{display:inline-block;font-size:.65rem;font-weight:700;padding:3px 10px;border-radius:12px;color:#fff;letter-spacing:.05em}
.option-size{font-size:2rem;font-weight:800;color:#0f172a;margin:8px 0 0}
.option-spend{font-size:.85rem;font-weight:600;color:#78350f;margin:2px 0 10px}
.option-desc{font-size:.87rem;color:#475569;line-height:1.55;margin-bottom:10px}
.option-when{font-size:.85rem;color:#334155;line-height:1.55;padding-top:10px;border-top:1px solid #f1f5f9}
.option-a{border-color:#e11d48;background:linear-gradient(180deg,#fef2f2 0%,#fff 60%)} .option-a .option-badge{background:#e11d48}
.option-b{border-color:#16a34a;background:linear-gradient(180deg,#f0fdf4 0%,#fff 60%)} .option-b .option-badge{background:#16a34a}
.option-c{border-color:#2E75B6;background:linear-gradient(180deg,#eff6ff 0%,#fff 60%)} .option-c .option-badge{background:#2E75B6}
.callout{border-radius:10px;padding:14px 18px;margin:12px 0;font-size:.95rem}
.callout.good{background:#dcfce7;border-left:4px solid #16a34a;color:#14532d}
.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:12px 0}
.card{background:#f8fafc;border-radius:10px;padding:16px;text-align:center;border-top:3px solid #16a34a}
.card .l{font-size:.72rem;color:#64748b;font-weight:600;text-transform:uppercase}
.card .v{font-size:1.5rem;font-weight:700;color:#0f172a;margin-top:6px}
.card .s{font-size:.72rem;color:#94a3b8;margin-top:3px}
.chbox{position:relative;height:300px;margin:12px 0}
.chbox.tall{height:360px}
table{width:100%;border-collapse:collapse;margin:12px 0;font-size:.86rem}
th{background:#0f172a;color:#fff;padding:10px 12px;text-align:left;font-size:.72rem;text-transform:uppercase}
td{padding:9px 12px;border-bottom:1px solid #f1f5f9}
.act-row{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:14px}
@media(max-width:850px){.act-row{grid-template-columns:1fr}}
.act-card{background:#fff;border-radius:12px;padding:20px 22px;border:2px solid #f1f5f9}
.act-card h3{font-size:1.05rem;font-weight:700;color:#0f172a;margin:8px 0 4px}
.act-badge{display:inline-block;font-size:.65rem;font-weight:700;padding:3px 10px;border-radius:12px;color:#fff}
.act-size{font-size:1.7rem;font-weight:700;color:#0f172a;margin:6px 0 0}
.act-money{font-size:.8rem;font-weight:600;color:#78350f;margin:4px 0 10px}
.act-desc{font-size:.85rem;color:#475569;line-height:1.55}
.act-protect{border-color:#16a34a;background:linear-gradient(180deg,#f0fdf4 0%,#fff 60%)} .act-protect .act-badge{background:#16a34a}
.act-grow{border-color:#2E75B6;background:linear-gradient(180deg,#eff6ff 0%,#fff 60%)} .act-grow .act-badge{background:#2E75B6}
.act-reengage{border-color:#e11d48;background:linear-gradient(180deg,#fef2f2 0%,#fff 60%)} .act-reengage .act-badge{background:#e11d48}
"""

JS_DATA = json.dumps(data_obj)

html = f"""<!DOCTYPE html>
<html lang='en'><head><meta charset='UTF-8'>
<title>Jetour — Audience Snapshot (Proxy Mode)</title>
<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'></script>
<script src='https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0'></script>
<style>@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');{CSS}</style>
</head><body>

<div id='hdr'>
<h1>Jetour — Audience Snapshot (Proxy Mode)</h1>
<p>Affordable innovation, SUV-first, tech-forward for a new market entrant</p>
<div class='meta'>Generated {esc(now)} · Rolling 12 months</div>
</div>

<div class='ctn'>

<div class='sec'>
<div class='proxy-notice'>
<h3>Why this is a proxy pitch</h3>
<p>
Jetour entered the SA market in September 2024. The brand does not yet appear at meaningful scale in FNB card data — car purchases largely happen through vehicle finance, not debit transactions, and the dealership network is still growing to 40+ locations.
</p>
<p style='margin-top:8px'>
This pitch shows <b>three proxy audiences</b> below. Pick the one that fits the client conversation. All downstream metrics (demographics, geography, activation) reflect <b>Option B — Value car audience</b> as the default view.
</p>
</div>

<h2>Choose your audience angle</h2>
<p class='sub'>Three ways to frame the Jetour opportunity, each with different reach vs precision trade-offs.</p>
{option_cards}
</div>

<div class='sec'>
<h2>Customer quality (Option B)</h2>
<p class='sub'>Value-vehicle customers clustered by FNB behavioural segmentation. Segments reflect FNB-wide activity.</p>
<div class='callout good'>
<b>{top_2}% of value-vehicle customers sit in FNB two highest-value segments</b> — the affordable-vehicle buyer is not necessarily a low-value customer, they choose value on purpose.
</div>
<div class='chbox'><canvas id='chSegments'></canvas></div>
</div>

<div class='sec'>
<h2>Who they are (Option B)</h2>
<div class='row'>{demo_row}</div>
</div>

<div class='sec'>
<h2>Income &amp; gender profile (Option B)</h2>
<div class='chbox tall'><canvas id='chIncomeGender'></canvas></div>
</div>

<div class='sec'>
<h2>Age &amp; gender profile (Option B)</h2>
<div class='chbox tall'><canvas id='chAgeGender'></canvas></div>
</div>

<div class='sec'>
<h2>Geographic footprint (Option B)</h2>
<p class='sub'>Total value-vehicle spend by province.</p>
<div class='chbox tall'><canvas id='chGeo'></canvas></div>
</div>

<div class='sec'>
<h2>Activation opportunities</h2>
<p class='sub'>Three pools within Option B, each with a different play and real spend attached.</p>
<div class='act-row'>
<div class='act-card act-protect'>
<div class='act-badge'>PROTECT</div>
<h3>Champions &amp; Loyal High Value</h3>
<div class='act-size'>{N(protect)}</div>
<div class='act-money'>{R(protect_s)} annual spend at stake</div>
<div class='act-desc'>Higher-value customers already in the value-vehicle market. Position Jetour on tech-forward features, in-car experience, and long-term ownership economics.</div>
</div>
<div class='act-card act-grow'>
<div class='act-badge'>GROW</div>
<h3>Steady Mid-Tier</h3>
<div class='act-size'>{N(grow)}</div>
<div class='act-money'>{R(grow_s)} current spend + upside</div>
<div class='act-desc'>Reliable value-vehicle buyers ready to trade up to SUV. Focus on the T-series, adventure positioning, and financing that matches their existing spend patterns.</div>
</div>
<div class='act-card act-reengage'>
<div class='act-badge'>ACQUIRE</div>
<h3>Dormant &amp; Emerging</h3>
<div class='act-size'>{N(reeng)}</div>
<div class='act-money'>{R(reeng_s)} lapsed spend to redirect</div>
<div class='act-desc'>Customers with fading engagement at current brands — prime targets for a new brand launch. Position Jetour as the fresh alternative to what they had before.</div>
</div>
</div>
</div>

<div class='sec'>
<h2>Adjacent spend — bundling &amp; co-brand opportunities</h2>
<p class='sub'>Top non-vehicle categories these customers spend in. Useful for launch-partner co-brands and channel targeting.</p>
<table><tr><th>Category</th><th>Shoppers</th><th>Annual spend</th></tr>{cross_rows}</table>
</div>

</div>

<script>
const Data = {JS_DATA};
const colors = {{ male:'#2E75B6', female:'#E85C0D', accent:'#1e3a5f', jetour:'#16a34a',
                  seg: ['#16a34a','#2E75B6','#f59e0b','#e11d48','#94a3b8'] }};
if (typeof ChartDataLabels !== 'undefined') Chart.register(ChartDataLabels);

function mkChart(id, cfg) {{
  const el = document.getElementById(id);
  if (!el) return;
  if (!cfg.options) cfg.options = {{}};
  if (!cfg.options.plugins) cfg.options.plugins = {{}};
  if (cfg.options.plugins.datalabels === undefined) cfg.options.plugins.datalabels = {{ display: false }};
  new Chart(el, cfg);
}}

mkChart('chIncomeGender', {{
  type: 'bar',
  data: {{ labels: Data.income_gender.map(r => r.band),
    datasets: [
      {{ label:'Male',   data: Data.income_gender.map(r => r.male),   backgroundColor: colors.male }},
      {{ label:'Female', data: Data.income_gender.map(r => r.female), backgroundColor: colors.female }}
    ]}},
  options: {{ responsive:true, maintainAspectRatio:false, scales: {{ y: {{ beginAtZero:true }} }} }}
}});

mkChart('chAgeGender', {{
  type: 'bar',
  data: {{ labels: Data.age_gender.map(r => r.band),
    datasets: [
      {{ label:'Male',   data: Data.age_gender.map(r => r.male),   backgroundColor: colors.male }},
      {{ label:'Female', data: Data.age_gender.map(r => r.female), backgroundColor: colors.female }}
    ]}},
  options: {{ responsive:true, maintainAspectRatio:false, scales: {{ y: {{ beginAtZero:true }} }} }}
}});

mkChart('chGeo', {{
  type: 'bar',
  data: {{ labels: Data.geo.map(r => r.province),
    datasets: [{{ label:'Spend', data: Data.geo.map(r => r.spend),
      backgroundColor: colors.jetour, borderColor:'#166534', borderWidth:1 }}]}},
  options: {{ indexAxis:'y', responsive:true, maintainAspectRatio:false,
    plugins: {{ legend: {{ display:false }} }},
    scales: {{ x: {{ beginAtZero:true, ticks: {{ callback: v => 'R' + (v/1e6).toFixed(0) + 'M' }} }} }} }}
}});

if (Data.segments.length > 0) {{
  mkChart('chSegments', {{
    type: 'doughnut',
    data: {{ labels: Data.segments.map(r => r.name + ' (' + r.pct.toFixed(1) + '%)'),
      datasets: [{{ data: Data.segments.map(r => r.customers),
        backgroundColor: Data.segments.map((_,i) => colors.seg[i % colors.seg.length]),
        borderColor:'#fff', borderWidth:3 }}]}},
    options: {{ responsive:true, maintainAspectRatio:false, cutout:'58%',
      plugins: {{
        legend: {{ position: 'right' }},
        datalabels: {{
          display: (ctx) => {{
            const total = ctx.chart.data.datasets[0].data.reduce((a,b) => a+b, 0);
            return (ctx.dataset.data[ctx.dataIndex]/total) * 100 >= 8;
          }},
          color:'#fff', font: {{ size: 14, weight: 'bold' }},
          formatter: (v, ctx) => {{
            const total = ctx.chart.data.datasets[0].data.reduce((a,b) => a+b, 0);
            return ((v/total)*100).toFixed(1) + '%';
          }}
        }}
      }} }}
  }});
}}
</script>

</body></html>
"""

OUT = 'jetour_pitch.html'
with open(OUT, 'w') as f:
    f.write(html)

print()
print(f'Wrote: {OUT}')
