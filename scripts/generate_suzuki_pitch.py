#!/usr/bin/env python3
"""
Suzuki — client-facing pitch. Direct mode (SUZUKI DESTINATION exists in data).

Positioning (from web research):
    - Practical, dependable value
    - Low total cost of ownership
    - Fuel-efficient compact-smart engineering
    - Family + cost-conscious urban buyers
    - SA growth story: 22% YoY, targeting 3x continental sales by 2030
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


# ── Queries ──────────────────────────────────────────────────────────────
print('Querying...')

hero = q(f"""
    SELECT
        COUNT(DISTINCT UNIQUE_ID)                                        AS customers,
        SUM(dest_txn_count)                                              AS transactions,
        ROUND(SUM(dest_spend), 0)                                        AS total_spend,
        ROUND(SUM(dest_spend) / NULLIF(SUM(dest_txn_count), 0), 2)       AS avg_txn_value,
        ROUND(SUM(dest_spend) / NULLIF(COUNT(DISTINCT UNIQUE_ID), 0), 0) AS spend_per_customer
    FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE UPPER(DESTINATION) = 'SUZUKI'
""").iloc[0]

# Category context (for positioning)
category = q(f"""
    SELECT
        COUNT(DISTINCT UNIQUE_ID) AS customers,
        ROUND(SUM(dest_spend), 0) AS spend
    FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE CATEGORY_TWO = 'Vehicle Maintenance & Dealerships'
""").iloc[0]

# Demographics
demo = q(f"""
    WITH custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE UPPER(DESTINATION) = 'SUZUKI'
    )
    SELECT
        COUNT(*)                                                              AS customers,
        ROUND(AVG(c.age), 1)                                                  AS avg_age,
        COUNT(DISTINCT CASE WHEN c.gender_label = 'Male'   THEN c.UNIQUE_ID END) AS male,
        COUNT(DISTINCT CASE WHEN c.gender_label = 'Female' THEN c.UNIQUE_ID END) AS female
    FROM custs f JOIN `{PROJECT}.staging.stg_customers` c USING (UNIQUE_ID)
""").iloc[0]

income_gender = q(f"""
    WITH custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE UPPER(DESTINATION) = 'SUZUKI'
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
        WHERE UPPER(DESTINATION) = 'SUZUKI'
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
        WHERE UPPER(DESTINATION) = 'SUZUKI'
    )
    SELECT t.PROVINCE AS province,
           COUNT(DISTINCT t.UNIQUE_ID) AS customers,
           ROUND(SUM(t.trns_amt), 0)   AS spend
    FROM custs f JOIN `{PROJECT}.staging.stg_transactions` t USING (UNIQUE_ID)
    WHERE UPPER(t.DESTINATION) = 'SUZUKI' AND t.PROVINCE IS NOT NULL
    GROUP BY t.PROVINCE
    ORDER BY spend DESC LIMIT 9
""").to_dict('records')

trend = q(f"""
    SELECT FORMAT_DATE('%Y-%m', t.EFF_DATE) AS month,
           COUNT(DISTINCT t.UNIQUE_ID) AS customers,
           ROUND(SUM(t.trns_amt), 0) AS spend
    FROM `{PROJECT}.staging.stg_transactions` t
    WHERE UPPER(t.DESTINATION) = 'SUZUKI'
    GROUP BY month ORDER BY month
""").to_dict('records')

segments = q(f"""
    WITH custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE UPPER(DESTINATION) = 'SUZUKI'
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
        WHERE UPPER(cs.DESTINATION) = 'SUZUKI'
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
        WHERE UPPER(DESTINATION) = 'SUZUKI'
    )
    SELECT cs.CATEGORY_TWO AS category,
           COUNT(DISTINCT cs.UNIQUE_ID) AS shoppers,
           ROUND(SUM(cs.dest_spend), 0) AS spend
    FROM custs f JOIN `{PROJECT}.analytics.int_customer_category_spend` cs USING (UNIQUE_ID)
    WHERE cs.CATEGORY_TWO <> 'Vehicle Maintenance & Dealerships'
    GROUP BY cs.CATEGORY_TWO
    ORDER BY shoppers DESC LIMIT 8
""").to_dict('records')

# Suzuki share of the vehicle category (positioning)
suzuki_share_pct = round(100 * int(hero['customers']) / int(category['customers']), 2)

print(f'  → Suzuki customers: {int(hero["customers"]):,}')
print(f'  → Suzuki spend: {R(hero["total_spend"])}')
print(f'  → Category share of Vehicle Maintenance & Dealerships: {suzuki_share_pct}% by customers')


# ── Bundle for Chart.js ──────────────────────────────────────────────────
data_obj = {
    'income_gender': [{'band': r['band'], 'male': int(r['male']), 'female': int(r['female'])} for r in income_gender],
    'age_gender':    [{'band': r['band'], 'male': int(r['male']), 'female': int(r['female'])} for r in age_gender],
    'geo':           [{'province': r['province'], 'customers': int(r['customers']), 'spend': float(r['spend'])} for r in geo],
    'trend':         [{'month': r['month'], 'customers': int(r['customers']), 'spend': float(r['spend'])} for r in trend],
    'segments':      [{'name': s['segment'], 'customers': int(s['customers']), 'pct': float(s['pct'])} for s in segments],
}

now = datetime.now().strftime('%d %B %Y')


def kpi(label, value, sub=''):
    sub_html = f'<div class="s">{esc(sub)}</div>' if sub else ''
    return f'<div class="card"><div class="l">{esc(label)}</div><div class="v">{esc(value)}</div>{sub_html}</div>'


hero_kpis = '<div class="row">' + ''.join([
    kpi('Customers', N(hero['customers']), 'unique FNB cardholders'),
    kpi('Annual Spend', R(hero['total_spend'])),
    kpi('Transactions', N(hero['transactions'])),
    kpi('Avg Basket', R(hero['avg_txn_value']), 'per visit'),
    kpi('Spend / Customer', R_exact(hero['spend_per_customer']), 'per year'),
    kpi('Avg Age', f"{demo['avg_age']}"),
]) + '</div>'

total_gender = int(demo['male']) + int(demo['female'])
demo_row = ''.join([
    kpi('Female', f'{round(100*demo["female"]/total_gender,1)}%', f'{N(demo["female"])} customers'),
    kpi('Male', f'{round(100*demo["male"]/total_gender,1)}%', f'{N(demo["male"])} customers'),
    kpi('Avg age', f'{demo["avg_age"]}', 'years'),
])

# Trend narrative
trend_narrative = ''
if len(trend) >= 3:
    fh, sh = trend[:len(trend)//2], trend[len(trend)//2:]
    af = sum(m['spend'] for m in fh) / len(fh)
    as_ = sum(m['spend'] for m in sh) / len(sh)
    d_pct = round(100 * (as_ - af) / max(af, 1), 1)
    peak = max(trend, key=lambda m: m['spend'])
    trough = min(trend, key=lambda m: m['spend'])
    if d_pct > 3:
        direction = f'<b style="color:#16a34a">growing</b> ({d_pct:+.1f}% H1→H2)'
    elif d_pct < -3:
        direction = f'<b style="color:#e11d48">softening</b> ({d_pct:+.1f}% H1→H2)'
    else:
        direction = f'<b style="color:#334155">stable</b> ({d_pct:+.1f}% H1→H2)'
    trend_narrative = (f'Suzuki monthly spend is {direction}. Peak: '
                       f'<b>{esc(peak["month"])}</b> ({R(peak["spend"])}). '
                       f'Softest: <b>{esc(trough["month"])}</b> ({R(trough["spend"])}).')

# Segments
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


CSS = """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#f8fafc;color:#1a202c}
#hdr{background:linear-gradient(135deg,#0f172a,#c8102e);color:#fff;padding:28px 32px}
#hdr h1{font-size:1.9rem;font-weight:700}
#hdr p{opacity:.9;font-size:1rem;margin-top:6px}
#hdr .meta{font-size:.78rem;opacity:.6;margin-top:14px}
.ctn{max-width:1200px;margin:0 auto;padding:24px}
.sec{background:#fff;border-radius:14px;padding:26px 30px;margin:18px 0;border:1px solid #f1f5f9;box-shadow:0 1px 4px rgba(0,0,0,.04)}
.sec h2{font-size:1.35rem;font-weight:700;color:#0f172a;margin-bottom:6px}
.sec .sub{color:#64748b;font-size:.92rem;margin-bottom:18px;line-height:1.5}
.hero{background:linear-gradient(135deg,#fef2f2,#fecaca);border:1px solid #c8102e}
.hero h2{color:#7f1d1d} .hero .sub{color:#991b1b}
.callout{border-radius:10px;padding:14px 18px;margin:12px 0;font-size:.95rem}
.callout.good{background:#dcfce7;border-left:4px solid #16a34a;color:#14532d}
.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:12px 0}
.card{background:#f8fafc;border-radius:10px;padding:16px;text-align:center;border-top:3px solid #c8102e}
.hero .card{background:#fff5f5;border-top-color:#c8102e}
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
.trend-story{background:#f1f5f9;border-radius:10px;padding:14px 18px;margin-top:14px;font-size:.94rem;color:#334155;line-height:1.55}
"""

JS_DATA = json.dumps(data_obj)

html = f"""<!DOCTYPE html>
<html lang='en'><head><meta charset='UTF-8'>
<title>Suzuki — Audience Snapshot</title>
<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'></script>
<script src='https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0'></script>
<style>@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');{CSS}</style>
</head><body>

<div id='hdr'>
<h1>Suzuki — Audience Snapshot</h1>
<p>Practical value, low total cost of ownership, fuel-efficient family motoring</p>
<div class='meta'>Generated {esc(now)} · Rolling 12 months</div>
</div>

<div class='ctn'>

<div class='sec hero'>
<h2>The reach story</h2>
<p class='sub'>Distinct FNB cardholders transacting at Suzuki dealerships and service points in the last 12 months.</p>
{hero_kpis}
</div>

<div class='sec'>
<h2>Category positioning</h2>
<p class='sub'>Where Suzuki sits in South Africa's Vehicle Maintenance and Dealerships category by FNB cardholder activity.</p>
<div class='row'>
{kpi('Category Share', f'{suzuki_share_pct}%', 'by unique customers')}
{kpi('Segment', 'Value & practicality', 'positioning')}
{kpi('Story', 'Growth market', '22% YoY across SA & Nigeria per Suzuki SA')}
{kpi('Category Base', N(category['customers']), 'total vehicle-active FNB customers')}
</div>
</div>

<div class='sec'>
<h2>Customer quality</h2>
<p class='sub'>Suzuki customers clustered by FNB behavioural segmentation. Segments reflect FNB-wide activity — practical value buyers should skew Steady Mid-Tier and Loyal High Value.</p>
<div class='callout good'>
<b>{top_2}% of Suzuki customers sit in FNB two highest-value segments</b> — a strong indicator that the "practical yet aspirational" positioning is landing.
</div>
<div class='chbox'><canvas id='chSegments'></canvas></div>
</div>

<div class='sec'>
<h2>Who they are</h2>
<div class='row'>{demo_row}</div>
<p class='sub' style='margin-top:14px'>
Suzuki's SA audience skews older and more family-oriented — matching Suzuki's global positioning around dependable value and low total cost of ownership.
</p>
</div>

<div class='sec'>
<h2>Income &amp; gender profile</h2>
<div class='chbox tall'><canvas id='chIncomeGender'></canvas></div>
</div>

<div class='sec'>
<h2>Age &amp; gender profile</h2>
<div class='chbox tall'><canvas id='chAgeGender'></canvas></div>
</div>

<div class='sec'>
<h2>Geographic footprint</h2>
<p class='sub'>Total Suzuki spend by province — the map of where Suzuki dealerships and service points are most active.</p>
<div class='chbox tall'><canvas id='chGeo'></canvas></div>
</div>

<div class='sec'>
<h2>Monthly trend</h2>
<p class='sub'>Suzuki spend and customer counts month-over-month across the last 12 months.</p>
<div class='chbox tall'><canvas id='chTrend'></canvas></div>
<div class='trend-story'>{trend_narrative}</div>
</div>

<div class='sec'>
<h2>Activation opportunities</h2>
<p class='sub'>Three pools within the audience, each with a different play and real spend attached.</p>
<div class='act-row'>
<div class='act-card act-protect'>
<div class='act-badge'>PROTECT</div>
<h3>Champions &amp; Loyal High Value</h3>
<div class='act-size'>{N(protect)}</div>
<div class='act-money'>{R(protect_s)} annual Suzuki spend at stake</div>
<div class='act-desc'>Your highest-value audience — repeat service customers and multi-vehicle families. Retain with service-plan upgrades, extended warranty offers, and next-vehicle upgrade paths.</div>
</div>
<div class='act-card act-grow'>
<div class='act-badge'>GROW</div>
<h3>Steady Mid-Tier</h3>
<div class='act-size'>{N(grow)}</div>
<div class='act-money'>{R(grow_s)} current spend + upside</div>
<div class='act-desc'>Reliable regulars ready to trade up. Focus on service-plan bundles, low-COO messaging, and family-sized model upgrades (Grand Vitara, Ertiga).</div>
</div>
<div class='act-card act-reengage'>
<div class='act-badge'>RE-ENGAGE</div>
<h3>Dormant &amp; At Risk</h3>
<div class='act-size'>{N(reeng)}</div>
<div class='act-money'>{R(reeng_s)} lapsed spend to recover</div>
<div class='act-desc'>Previously active Suzuki customers who have gone quiet — likely gone to competitors. Win-back with trade-in offers, refreshed service pricing, and fuel-cost comparisons.</div>
</div>
</div>
</div>

<div class='sec'>
<h2>Adjacent spend — bundling &amp; co-brand opportunities</h2>
<p class='sub'>Top categories Suzuki customers spend in beyond the dealership. Useful for bundle offers (insurance, tracking, fuel programmes) and co-brand campaigns.</p>
<table><tr><th>Category</th><th>Shoppers</th><th>Annual spend</th></tr>{cross_rows}</table>
</div>

</div>

<script>
const Data = {JS_DATA};
const colors = {{ male:'#2E75B6', female:'#E85C0D', accent:'#1e3a5f', suzuki:'#c8102e',
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
      backgroundColor: colors.suzuki, borderColor:'#7f1d1d', borderWidth:1 }}]}},
  options: {{ indexAxis:'y', responsive:true, maintainAspectRatio:false,
    plugins: {{ legend: {{ display:false }} }},
    scales: {{ x: {{ beginAtZero:true, ticks: {{ callback: v => 'R' + (v/1e6).toFixed(1) + 'M' }} }} }} }}
}});

mkChart('chTrend', {{
  type: 'line',
  data: {{ labels: Data.trend.map(r => r.month),
    datasets: [
      {{ label:'Spend', data: Data.trend.map(r => r.spend),
        borderColor: colors.suzuki, backgroundColor:'rgba(200,16,46,0.15)',
        yAxisID:'y', tension:0.3, fill:true }},
      {{ label:'Customers', data: Data.trend.map(r => r.customers),
        borderColor: colors.accent, backgroundColor:'transparent',
        yAxisID:'y1', tension:0.3 }}
    ]}},
  options: {{ responsive:true, maintainAspectRatio:false,
    scales: {{
      y:  {{ position:'left',  ticks: {{ callback: v => 'R' + (v/1e6).toFixed(1) + 'M' }} }},
      y1: {{ position:'right', grid: {{ drawOnChartArea:false }},
              ticks: {{ callback: v => (v/1e3).toFixed(1) + 'k' }} }}
    }} }}
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

OUT = 'suzuki_pitch.html'
with open(OUT, 'w') as f:
    f.write(html)

print()
print(f'Wrote: {OUT}')
