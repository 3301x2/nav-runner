#!/usr/bin/env python3
"""
Takealot CLIENT-FACING pitch - screenshot-ready HTML.
Direct mode: single DESTINATION='TAKEALOT', CATEGORY_TWO='General Shopping'.

Framing note: our category taxonomy tags Takealot's competitive comps
under Digital Media/Gaming/Apps rather than online retail, so the
competitive comparison uses cross-shop against mainstream retailers
(PnP, Checkers, Woolies) to show Takealot's audience is South Africa's
mainstream retail spender who also shops online.

Usage:
  python3 scripts/generate_takealot_pitch.py [sandbox|production]
Output:
  takealot_pitch.html
"""
from __future__ import annotations
import html as _h
import json
import subprocess
import sys
from datetime import datetime


REQUIRED = {
  'pandas':        'pandas',
  'db_dtypes':       'db-dtypes',
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
bq = bigquery.Client(project=PROJECT, location='africa-south1')


def q(sql: str) -> pd.DataFrame:
  return bq.query(sql, location='africa-south1').to_dataframe()


def R(v) -> str:
  if v is None or pd.isna(v): return 'N/A'
  v = float(v)
  if abs(v) >= 1e9: return f'R{v/1e9:.2f}B'
  if abs(v) >= 1e6: return f'R{v/1e6:.1f}M'
  if abs(v) >= 1e3: return f'R{v/1e3:.0f}k'
  return f'R{v:,.0f}'


def R_exact(v) -> str:
  if v is None or pd.isna(v): return 'N/A'
  return f'R{float(v):,.0f}'


def N(v) -> str:
  if v is None or pd.isna(v): return 'N/A'
  return f'{int(v):,}'


def esc(s) -> str:
  return _h.escape(str(s))


DEST = 'TAKEALOT'
BRAND_NAME = 'Takealot'
BRAND_COLOR = '#00A0DC'  # Takealot teal-blue

# ── Queries ─────────────────────────────────────────────────────────────
print('Querying...')

hero = q(f"""
  SELECT
    COUNT(DISTINCT UNIQUE_ID)                    AS customers,
    SUM(dest_txn_count)                       AS transactions,
    ROUND(SUM(dest_spend), 0)                    AS total_spend,
    ROUND(SUM(dest_spend) / NULLIF(SUM(dest_txn_count), 0), 2)    AS avg_txn_value,
    ROUND(SUM(dest_spend) / NULLIF(COUNT(DISTINCT UNIQUE_ID), 0), 0) AS spend_per_customer
  FROM `{PROJECT}.analytics.int_customer_category_spend`
  WHERE UPPER(DESTINATION) = '{DEST}'
""").iloc[0]

# Category benchmarks (rank, wallet share, category share)
takealot_bench = q(f"""
  SELECT
    CATEGORY_TWO,
    ROUND(market_share_pct, 1)       AS category_share_pct,
    ROUND(penetration_pct, 1)        AS category_reach_pct,
    ROUND(avg_share_of_wallet, 1)    AS wallet_share_pct,
    spend_rank
  FROM `{PROJECT}.marts.mart_destination_benchmarks`
  WHERE UPPER(DESTINATION) = '{DEST}'
""")
tbench = takealot_bench.iloc[0] if not takealot_bench.empty else None

# Demographics
demo = q(f"""
  WITH custs AS (
    SELECT DISTINCT UNIQUE_ID
    FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE UPPER(DESTINATION) = '{DEST}'
  )
  SELECT
    COUNT(*)                               AS customers,
    ROUND(AVG(c.age), 1)                         AS avg_age,
    COUNT(DISTINCT CASE WHEN c.gender_label = 'Male'  THEN c.UNIQUE_ID END) AS male,
    COUNT(DISTINCT CASE WHEN c.gender_label = 'Female' THEN c.UNIQUE_ID END) AS female
  FROM custs f
  JOIN `{PROJECT}.staging.stg_customers` c USING (UNIQUE_ID)
""").iloc[0]

income_gender = q(f"""
  WITH custs AS (
    SELECT DISTINCT UNIQUE_ID
    FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE UPPER(DESTINATION) = '{DEST}'
  )
  SELECT
    c.income_group AS band,
    COUNT(DISTINCT CASE WHEN c.gender_label = 'Male'  THEN c.UNIQUE_ID END) AS male,
    COUNT(DISTINCT CASE WHEN c.gender_label = 'Female' THEN c.UNIQUE_ID END) AS female
  FROM custs f
  JOIN `{PROJECT}.staging.stg_customers` c USING (UNIQUE_ID)
  WHERE c.income_group IS NOT NULL AND c.income_group <> 'Unknown'
  GROUP BY c.income_group
  ORDER BY
   CASE c.income_group
    WHEN 'R0-R5.5k' THEN 1 WHEN 'R5.5k-R13.5k' THEN 2
    WHEN 'R13.5k-R23.5k' THEN 3 WHEN 'R23.5k-R32.5k' THEN 4
    WHEN 'R32.5k-R56k' THEN 5 WHEN 'R56k+' THEN 6 ELSE 99
   END
""").to_dict('records')

age_gender = q(f"""
  WITH custs AS (
    SELECT DISTINCT UNIQUE_ID
    FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE UPPER(DESTINATION) = '{DEST}'
  )
  SELECT
    c.age_group AS band,
    COUNT(DISTINCT CASE WHEN c.gender_label = 'Male'  THEN c.UNIQUE_ID END) AS male,
    COUNT(DISTINCT CASE WHEN c.gender_label = 'Female' THEN c.UNIQUE_ID END) AS female
  FROM custs f
  JOIN `{PROJECT}.staging.stg_customers` c USING (UNIQUE_ID)
  WHERE c.age_group IS NOT NULL AND c.age_group <> 'Unknown'
  GROUP BY c.age_group
  ORDER BY
   CASE c.age_group
    WHEN '18-25' THEN 1 WHEN '26-35' THEN 2
    WHEN '36-45' THEN 3 WHEN '46-60' THEN 4 WHEN '60+' THEN 5 ELSE 99
   END
""").to_dict('records')

geo = q(f"""
  WITH custs AS (
    SELECT DISTINCT UNIQUE_ID
    FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE UPPER(DESTINATION) = '{DEST}'
  )
  SELECT
    t.PROVINCE AS province,
    COUNT(DISTINCT t.UNIQUE_ID) AS customers,
    ROUND(SUM(t.trns_amt), 0)  AS spend
  FROM custs f
  JOIN `{PROJECT}.staging.stg_transactions` t USING (UNIQUE_ID)
  WHERE UPPER(t.DESTINATION) = '{DEST}'
   AND t.PROVINCE IS NOT NULL
  GROUP BY t.PROVINCE
  ORDER BY spend DESC
  LIMIT 9
""").to_dict('records')

segments = q(f"""
  WITH custs AS (
    SELECT DISTINCT UNIQUE_ID
    FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE UPPER(DESTINATION) = '{DEST}'
  )
  SELECT
    co.segment_name AS segment,
    COUNT(*)                       AS customers,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)  AS pct
  FROM custs f
  JOIN `{PROJECT}.marts.mart_cluster_output` co USING (UNIQUE_ID)
  GROUP BY co.segment_name
  ORDER BY customers DESC
""").to_dict('records')

# Cross-shop - Takealot customers' spend at mainstream retailers
# This is the story: Takealot customers ARE mainstream retail customers
cross_shop_retail = q(f"""
  WITH custs AS (
    SELECT DISTINCT UNIQUE_ID
    FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE UPPER(DESTINATION) = '{DEST}'
  ),
  total_custs AS (SELECT COUNT(*) AS n FROM custs)
  SELECT
    cs.DESTINATION AS destination,
    COUNT(DISTINCT cs.UNIQUE_ID) AS shoppers,
    ROUND(SUM(cs.dest_spend), 0) AS spend,
    ROUND(100.0 * COUNT(DISTINCT cs.UNIQUE_ID) / (SELECT n FROM total_custs), 1) AS pct_of_takealot
  FROM custs f
  JOIN `{PROJECT}.analytics.int_customer_category_spend` cs USING (UNIQUE_ID)
  WHERE UPPER(cs.DESTINATION) IN (
    'PICK N PAY','CHECKERS','WOOLWORTHS','SHOPRITE','SPAR',
    'CHECKERS SIXTY60','FOOD LOVERS MARKET','WOOLWORTHS FOOD',
    'MR PRICE','H&M','ZARA','SUPERBALIST','BASH','MAKRO','GAME'
  )
  GROUP BY cs.DESTINATION
  ORDER BY shoppers DESC
  LIMIT 10
""").to_dict('records')

# Adjacent category cross-shop
cross_shop = q(f"""
  WITH custs AS (
    SELECT DISTINCT UNIQUE_ID
    FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE UPPER(DESTINATION) = '{DEST}'
  )
  SELECT
    cs.CATEGORY_TWO AS category,
    COUNT(DISTINCT cs.UNIQUE_ID) AS shoppers,
    ROUND(SUM(cs.dest_spend), 0) AS spend
  FROM custs f
  JOIN `{PROJECT}.analytics.int_customer_category_spend` cs USING (UNIQUE_ID)
  WHERE cs.CATEGORY_TWO <> 'General Shopping'
  GROUP BY cs.CATEGORY_TWO
  ORDER BY shoppers DESC
  LIMIT 10
""").to_dict('records')

# Monthly trend
trend = q(f"""
  SELECT
    FORMAT_DATE('%Y-%m', t.EFF_DATE) AS month,
    COUNT(DISTINCT t.UNIQUE_ID)   AS customers,
    ROUND(SUM(t.trns_amt), 0)    AS spend
  FROM `{PROJECT}.staging.stg_transactions` t
  WHERE UPPER(t.DESTINATION) = '{DEST}'
  GROUP BY month
  ORDER BY month
""").to_dict('records')

# Spend at Takealot per segment
segment_spend = q(f"""
  WITH activity AS (
    SELECT
      cs.UNIQUE_ID,
      SUM(cs.dest_spend) AS spend
    FROM `{PROJECT}.analytics.int_customer_category_spend` cs
    WHERE UPPER(cs.DESTINATION) = '{DEST}'
    GROUP BY cs.UNIQUE_ID
  )
  SELECT
    co.segment_name AS segment,
    COUNT(*) AS customers,
    ROUND(SUM(f.spend), 0) AS annual_spend
  FROM activity f
  JOIN `{PROJECT}.marts.mart_cluster_output` co USING (UNIQUE_ID)
  GROUP BY co.segment_name
""").to_dict('records')

print(' → data collected')


# ── Bundle for Chart.js ─────────────────────────────────────────────────
data_obj = {
  'income_gender': [{'band': str(r['band']), 'male': int(r['male']), 'female': int(r['female'])} for r in income_gender],
  'age_gender':  [{'band': str(r['band']), 'male': int(r['male']), 'female': int(r['female'])} for r in age_gender],
  'geo':      [{'province': str(r['province']), 'customers': int(r['customers']), 'spend': float(r['spend'])} for r in geo],
  'segments':   [{'name': str(r['segment']), 'customers': int(r['customers']), 'pct': float(r['pct'])} for r in segments],
  'cross_shop':  [{'category': str(r['category']), 'shoppers': int(r['shoppers']), 'spend': float(r['spend'])} for r in cross_shop],
  'trend':     [{'month': str(r['month']), 'customers': int(r['customers']), 'spend': float(r['spend'])} for r in trend],
}


def kpi_card(label: str, value: str, sub: str = '') -> str:
  sub_html = f'<div class="s">{esc(sub)}</div>' if sub else ''
  return (f'<div class="card"><div class="l">{esc(label)}</div>'
      f'<div class="v">{esc(value)}</div>{sub_html}</div>')


now = datetime.now().strftime('%d %B %Y')

if trend:
  first_month = str(trend[0]['month'])
  last_month  = str(trend[-1]['month'])
  timeframe_text = f'Transactions cover the 12 months from {first_month} to {last_month}.'
else:
  timeframe_text = 'Transactions cover the last 12 months.'

# Trend narrative
trend_narrative = ''
if len(trend) >= 3:
  first_half = trend[:len(trend)//2]
  second_half = trend[len(trend)//2:]
  avg_first  = sum(m['spend'] for m in first_half) / len(first_half)
  avg_second = sum(m['spend'] for m in second_half) / len(second_half)
  direction_pct = round(100 * (avg_second - avg_first) / max(avg_first, 1), 1)
  peak = max(trend, key=lambda m: m['spend'])
  trough = min(trend, key=lambda m: m['spend'])
  if direction_pct > 3:
    direction = f'<b style="color:#16a34a">growing</b> ({direction_pct:+.1f}% H1→H2)'
  elif direction_pct < -3:
    direction = f'<b style="color:#e11d48">softening</b> ({direction_pct:+.1f}% H1→H2)'
  else:
    direction = f'<b style="color:#334155">stable</b> ({direction_pct:+.1f}% H1→H2)'
  trend_narrative = (
    f'{BRAND_NAME} monthly spend is {direction}. Peak month: '
    f'<b>{esc(peak["month"])}</b> ({R(peak["spend"])}). '
    f'Softest month: <b>{esc(trough["month"])}</b> ({R(trough["spend"])}).'
  )

# Activation buckets
seg_by_name = {s['segment']: s for s in segments}
seg_spend_by_name = {s['segment']: s for s in segment_spend}
def _seg(name, key='customers'):
  row = seg_by_name.get(name)
  return int(row[key]) if row else 0
def _seg_spend(name):
  row = seg_spend_by_name.get(name)
  return int(row['annual_spend']) if row else 0

grow_pool   = _seg('Steady Mid-Tier')
protect_pool = _seg('Champions') + _seg('Loyal High Value')
reengage_pool = _seg('At Risk') + _seg('Dormant')

protect_spend = _seg_spend('Champions') + _seg_spend('Loyal High Value')
grow_spend   = _seg_spend('Steady Mid-Tier')
reengage_spend = _seg_spend('At Risk') + _seg_spend('Dormant')

activation_cards = ''.join([
  f'''<div class="act-card act-protect">
   <div class="act-badge">PROTECT</div>
   <h3>Champions &amp; Loyal High Value</h3>
   <div class="act-size">{N(protect_pool)}</div>
   <div class="act-money">{R(protect_spend)} annual spend at stake</div>
   <div class="act-desc">Your highest value online shoppers. The digital-first consumers who default to Takealot for anything from tech to household. Retention plays: TakealotMore/PlusOne perks, early access to sales, curated recommendations across categories they already spend in.</div>
  </div>''',
  f'''<div class="act-card act-grow">
   <div class="act-badge">GROW</div>
   <h3>Steady Mid-Tier</h3>
   <div class="act-size">{N(grow_pool)}</div>
   <div class="act-money">{R(grow_spend)} current spend · upside potential</div>
   <div class="act-desc">Reliable buyers ready to expand basket. Category-cross promos (moving them from single-category buyers into multi-category), payment-flexibility offers (Mobicred, layby), and delivery-value bundles.</div>
  </div>''',
  f'''<div class="act-card act-reengage">
   <div class="act-badge">RE-ENGAGE</div>
   <h3>Dormant &amp; At Risk</h3>
   <div class="act-size">{N(reengage_pool)}</div>
   <div class="act-money">{R(reengage_spend)} lapsed spend to recover</div>
   <div class="act-desc">Previously active online shoppers with fading engagement. Win-back with personalised offers on their last-purchased categories, free-delivery vouchers, and reminders of items still on their wishlist.</div>
  </div>''',
])

hero_kpis = '<div class="row">' + ''.join([
  kpi_card('Customers', N(hero['customers']), 'unique FNB cardholders'),
  kpi_card('Annual Spend', R(hero['total_spend'])),
  kpi_card('Transactions', N(hero['transactions'])),
  kpi_card('Avg Basket', R(hero['avg_txn_value'])),
  kpi_card('Spend / Customer', R_exact(hero['spend_per_customer']), 'per year'),
  kpi_card('Avg Age', f"{demo['avg_age']}"),
]) + '</div>'

total_gender = int(demo['male']) + int(demo['female'])
demo_row = ''.join([
  kpi_card('Female', f"{round(100*demo['female']/total_gender,1)}%", f"{N(demo['female'])} customers"),
  kpi_card('Male',  f"{round(100*demo['male']/total_gender,1)}%",  f"{N(demo['male'])} customers"),
  kpi_card('Avg age', f"{demo['avg_age']}", 'years'),
])

top_2_segments_pct = round(sum(s['pct'] for s in segments[:2]), 1) if len(segments) >= 2 else 0

cross_shop_rows = ''
for r in cross_shop:
  cross_shop_rows += (f'<tr><td>{esc(r["category"])}</td>'
            f'<td>{N(r["shoppers"])}</td>'
            f'<td>{R(r["spend"])}</td></tr>')

# Cross-shop retail table (Takealot customers who also shop mainstream retail)
retail_rows = ''
for r in cross_shop_retail:
  retail_rows += (f'<tr><td>{esc(r["destination"])}</td>'
          f'<td>{N(r["shoppers"])}</td>'
          f'<td>{r["pct_of_takealot"]:.1f}%</td>'
          f'<td>{R(r["spend"])}</td></tr>')


html = f"""<!DOCTYPE html>
<html lang='en'><head><meta charset='UTF-8'>
<title>{BRAND_NAME}, Audience Snapshot</title>
<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'></script>
<script src='https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0'></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'DM Sans',sans-serif; background:#f8fafc; color:#1a202c; }}
#hdr {{ background:linear-gradient(135deg,#001a2c,{BRAND_COLOR}); color:#fff; padding:28px 32px; }}
#hdr h1 {{ font-size:1.9rem; font-weight:700; }}
#hdr p {{ opacity:.9; font-size:1rem; margin-top:6px; }}
#hdr .meta {{ font-size:.78rem; opacity:.6; margin-top:14px; }}
.ctn {{ max-width:1200px; margin:0 auto; padding:24px; }}
.sec {{ background:#fff; border-radius:14px; padding:26px 30px; margin:18px 0; border:1px solid #f1f5f9; box-shadow:0 1px 4px rgba(0,0,0,.04); }}
.sec h2 {{ font-size:1.35rem; font-weight:700; color:#0f172a; margin-bottom:6px; }}
.sec .sub {{ color:#64748b; font-size:.92rem; margin-bottom:18px; line-height:1.5; }}
.hero {{ background:linear-gradient(135deg,#e0f4fb,#b8e4f2); border:1px solid {BRAND_COLOR}; }}
.hero h2 {{ color:#003a55; }}
.hero .sub {{ color:#005a80; }}
.callout {{ background:#dcfce7; border-left:4px solid #16a34a; border-radius:0 10px 10px 0; padding:14px 18px; margin:14px 0; font-size:.95rem; color:#14532d; line-height:1.5; }}
.row {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:12px 0; }}
.card {{ background:#f8fafc; border-radius:10px; padding:16px; text-align:center; border-top:3px solid {BRAND_COLOR}; }}
.hero .card {{ background:#eff9fd; border-top-color:{BRAND_COLOR}; }}
.card .l {{ font-size:.72rem; color:#64748b; font-weight:600; text-transform:uppercase; letter-spacing:.03em; }}
.card .v {{ font-size:1.5rem; font-weight:700; color:#0f172a; margin-top:6px; }}
.card .s {{ font-size:.72rem; color:#94a3b8; margin-top:3px; }}
.chbox {{ position:relative; height:300px; margin:12px 0; }}
.chbox.tall {{ height:360px; }}
.two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
@media(max-width:800px) {{ .two-col {{ grid-template-columns:1fr; }} }}
table {{ width:100%; border-collapse:collapse; margin:12px 0; font-size:.86rem; }}
th {{ background:#001a2c; color:#fff; padding:10px 12px; text-align:left; font-size:.72rem; text-transform:uppercase; letter-spacing:.03em; }}
td {{ padding:9px 12px; border-bottom:1px solid #f1f5f9; }}
.timeframe {{ font-size:.82rem; color:#64748b; margin-top:10px; font-style:italic; }}
.act-row {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-top:14px; }}
@media(max-width:850px) {{ .act-row {{ grid-template-columns:1fr; }} }}
.act-card {{ background:#fff; border-radius:12px; padding:20px 22px; border:2px solid #f1f5f9; position:relative; }}
.act-card h3 {{ font-size:1.05rem; font-weight:700; color:#0f172a; margin:8px 0 4px; }}
.act-badge {{ display:inline-block; font-size:.65rem; font-weight:700; padding:3px 10px; border-radius:12px; letter-spacing:.06em; color:#fff; }}
.act-size {{ font-size:1.7rem; font-weight:700; color:#0f172a; margin:6px 0 0; font-variant-numeric:tabular-nums; }}
.act-money {{ font-size:.8rem; font-weight:600; color:#003a55; margin:4px 0 10px; letter-spacing:.01em; }}
.act-desc {{ font-size:.85rem; color:#475569; line-height:1.55; }}
.act-protect {{ border-color:#16a34a; background:linear-gradient(180deg,#f0fdf4 0%,#fff 60%); }}
.act-protect .act-badge {{ background:#16a34a; }}
.act-grow   {{ border-color:{BRAND_COLOR}; background:linear-gradient(180deg,#eff9fd 0%,#fff 60%); }}
.act-grow   .act-badge {{ background:{BRAND_COLOR}; }}
.act-reengage {{ border-color:#e11d48; background:linear-gradient(180deg,#fef2f2 0%,#fff 60%); }}
.act-reengage .act-badge {{ background:#e11d48; }}
.trend-story {{ background:#f1f5f9; border-radius:10px; padding:14px 18px; margin-top:14px; font-size:.94rem; color:#334155; line-height:1.55; }}
</style>
</head><body>

<div id='hdr'>
<h1>{BRAND_NAME}, Audience Snapshot</h1>
<p>FNB cardholder activity at {BRAND_NAME}, last 12 months</p>
<div class='meta'>Generated {esc(now)}</div>
</div>

<div class='ctn'>

<div class='sec hero'>
<h2>The reach story</h2>
<p class='sub'>Distinct FNB cardholders shopping at {BRAND_NAME} in the last 12 months. A real, addressable audience of digitally active South African consumers.</p>
{hero_kpis}
</div>

<div class='sec'>
<h2>Category positioning</h2>
<p class='sub'>Where {BRAND_NAME} sits in the {esc(tbench['CATEGORY_TWO']) if tbench is not None else 'General Shopping'} category by FNB cardholder spend, plus the wallet-share view: what percentage of the average {BRAND_NAME} customer's category basket lands here.</p>
<div class='row'>
{f'''{kpi_card('Category Rank', f"#{int(tbench['spend_rank'])}", f"in {tbench['CATEGORY_TWO']}")}
     {kpi_card('Category Share', f"{tbench['category_share_pct']}%", 'by spend')}
     {kpi_card('Customer Reach', f"{tbench['category_reach_pct']}%", 'of category shoppers')}
     {kpi_card('Wallet Share', f"{tbench['wallet_share_pct']}%", 'of category basket')}''' if tbench is not None else ''}
</div>
<div class='callout' style='margin-top:14px'>
Wallet Share is the loyalty metric. It tells you how much of a customer's category basket already lands with {BRAND_NAME}. Growing Wallet Share compounds faster than acquiring net-new customers.
</div>
</div>

<div class='sec'>
<h2>Customer quality</h2>
<p class='sub'>{BRAND_NAME} customers clustered by FNB's behavioural segmentation model. Segments reflect FNB-wide activity, not {BRAND_NAME}-specific.</p>
<div class='callout'>
<b>{top_2_segments_pct}% of {BRAND_NAME} customers are in FNB's two highest-value segments.</b> Your platform pulls in the same shoppers driving premium retail activity across the FNB ecosystem.
</div>
<div class='two-col'>
<div class='chbox'><canvas id='chSegments'></canvas></div>
<div style='font-size:.88rem;line-height:1.6;color:#334155'>
<h3 style='font-size:1rem;color:#0f172a;margin-bottom:8px'>What the segments mean</h3>
<p><b style='color:#16a34a'>Loyal High Value.</b> Consistently high spenders with strong recency. Top of the funnel.</p>
<p style='margin-top:8px'><b style='color:{BRAND_COLOR}'>Champions.</b> Highest lifetime value, broad category spread, frequent transactions.</p>
<p style='margin-top:8px'><b style='color:#f59e0b'>Steady Mid-Tier.</b> Reliable regulars with moderate but stable spend patterns.</p>
<p style='margin-top:8px'><b style='color:#e11d48'>Dormant.</b> Previously active but low recent engagement. Re-activation opportunity.</p>
<p style='margin-top:8px'><b style='color:#94a3b8'>At Risk.</b> Spend and frequency declining. Win-back campaign candidates.</p>
</div>
</div>
</div>

<div class='sec'>
<h2>Who they are</h2>
<p class='sub'>A snapshot of the {BRAND_NAME} audience demographics.</p>
<div class='row'>
{demo_row}
</div>
</div>

<div class='sec'>
<h2>Income &amp; gender profile</h2>
<p class='sub'>Number of customers per income band, split by gender.</p>
<div class='chbox tall'><canvas id='chIncomeGender'></canvas></div>
</div>

<div class='sec'>
<h2>Age &amp; gender profile</h2>
<div class='chbox tall'><canvas id='chAgeGender'></canvas></div>
</div>

<div class='sec'>
<h2>Geographic footprint</h2>
<p class='sub'>Total {BRAND_NAME} spend by province. Where the audience lives.</p>
<div class='chbox tall'><canvas id='chGeo'></canvas></div>
</div>

<div class='sec'>
<h2>Monthly trend</h2>
<p class='sub'>{BRAND_NAME} spend and customer counts month-over-month across the last 12 months.</p>
<div class='chbox tall'><canvas id='chTrend'></canvas></div>
<div class='trend-story'>{trend_narrative}</div>
</div>

<div class='sec'>
<h2>Activation opportunities</h2>
<p class='sub'>The audience is three distinct pools. Each has a different play, and a real spend number attached.</p>
<div class='act-row'>
{activation_cards}
</div>
</div>

<div class='sec' style='background:linear-gradient(180deg,#eff9fd 0%,#fff 40%); border:2px solid {BRAND_COLOR}'>
<h2 style='color:#003a55'>Cross-shop with mainstream retail</h2>
<p class='sub'>{BRAND_NAME} customers are not "digital-only". They are South Africa's mainstream retail spender. Below is the overlap between {BRAND_NAME} customers and the biggest physical retail destinations in FNB card data.</p>
<table><tr><th>Retailer</th><th>Overlapping Customers</th><th>% of {BRAND_NAME} audience</th><th>Their spend at that retailer</th></tr>{retail_rows}</table>
<div class='callout' style='margin-top:14px'>
This overlap is the pitch. {BRAND_NAME} lets a brand reach the same aspirational shoppers who fill supermarket, apparel and department store baskets, with digital-native intent and buying context.
</div>
</div>

<div class='sec'>
<h2>Adjacent spend, bundling and co-brand opportunities</h2>
<p class='sub'>The top non-{BRAND_NAME} categories your customers already spend in. Useful for bundle offers, co-brand partnerships, and channel targeting.</p>
<table><tr><th>Category</th><th>Shoppers</th><th>Annual spend</th></tr>{cross_shop_rows}</table>
</div>

<div class='sec' style='background:#f8fafc; border:1px solid #e2e8f0;'>
<h2>Scope and timeframe</h2>
<p class='sub'>This view covers a single destination (DESTINATION = "TAKEALOT", CATEGORY_TWO = "General Shopping").</p>
<p class='timeframe'>{timeframe_text}</p>
</div>

</div>

<script>
const Data = {json.dumps(data_obj)};
const colors = {{
  male:  '#2E75B6',
  female: '#E85C0D',
  brand:  '{BRAND_COLOR}',
  accent: '#001a2c',
  seg:   ['#16a34a','{BRAND_COLOR}','#f59e0b','#e11d48','#94a3b8'],
}};

if (typeof ChartDataLabels !== 'undefined') {{ Chart.register(ChartDataLabels); }}

function mkChart(id, cfg) {{
  const el = document.getElementById(id); if (!el) return;
  if (!cfg.options) cfg.options = {{}};
  if (!cfg.options.plugins) cfg.options.plugins = {{}};
  if (cfg.options.plugins.datalabels === undefined) cfg.options.plugins.datalabels = {{ display:false }};
  new Chart(el, cfg);
}}

mkChart('chSegments', {{
  type: 'doughnut',
  data: {{
    labels: Data.segments.map(r => r.name + ' (' + r.pct.toFixed(1) + '%)'),
    datasets: [{{
      data: Data.segments.map(r => r.customers),
      backgroundColor: Data.segments.map((_,i) => colors.seg[i % colors.seg.length]),
      borderColor: '#fff', borderWidth: 3
    }}]
  }},
  options: {{
    responsive:true, maintainAspectRatio:false, cutout:'58%',
    plugins: {{
      legend: {{ position:'right', labels:{{ font:{{size:12}}, padding:12 }} }},
      datalabels: {{
        display: (ctx) => {{
          const total = ctx.chart.data.datasets[0].data.reduce((a,b)=>a+b,0);
          return (ctx.dataset.data[ctx.dataIndex]/total)*100 >= 8;
        }},
        color:'#fff', font:{{size:14, weight:'bold'}},
        formatter: (v, ctx) => {{
          const total = ctx.chart.data.datasets[0].data.reduce((a,b)=>a+b,0);
          return ((v/total)*100).toFixed(1)+'%';
        }}
      }}
    }}
  }}
}});

mkChart('chIncomeGender', {{
  type: 'bar',
  data: {{
    labels: Data.income_gender.map(r => r.band),
    datasets: [
      {{ label:'Male',  data: Data.income_gender.map(r => r.male),  backgroundColor: colors.male  }},
      {{ label:'Female', data: Data.income_gender.map(r => r.female), backgroundColor: colors.female }}
    ]
  }},
  options: {{ responsive:true, maintainAspectRatio:false, scales:{{ y:{{ beginAtZero:true }} }} }}
}});

mkChart('chAgeGender', {{
  type: 'bar',
  data: {{
    labels: Data.age_gender.map(r => r.band),
    datasets: [
      {{ label:'Male',  data: Data.age_gender.map(r => r.male),  backgroundColor: colors.male  }},
      {{ label:'Female', data: Data.age_gender.map(r => r.female), backgroundColor: colors.female }}
    ]
  }},
  options: {{ responsive:true, maintainAspectRatio:false, scales:{{ y:{{ beginAtZero:true }} }} }}
}});

mkChart('chGeo', {{
  type: 'bar',
  data: {{
    labels: Data.geo.map(r => r.province),
    datasets: [{{
      label:'Spend', data: Data.geo.map(r => r.spend),
      backgroundColor: colors.brand, borderColor: colors.accent, borderWidth:1
    }}]
  }},
  options: {{
    indexAxis:'y', responsive:true, maintainAspectRatio:false,
    plugins:{{ legend:{{ display:false }} }},
    scales:{{ x:{{ beginAtZero:true, ticks:{{ callback: v => 'R'+(v/1e6).toFixed(0)+'M' }} }} }}
  }}
}});

mkChart('chTrend', {{
  type: 'line',
  data: {{
    labels: Data.trend.map(r => r.month),
    datasets: [
      {{ label:'Spend', data: Data.trend.map(r => r.spend),
        borderColor: colors.brand, backgroundColor:'rgba(0,160,220,0.15)',
        yAxisID:'y', tension:0.3, fill:true }},
      {{ label:'Customers', data: Data.trend.map(r => r.customers),
        borderColor: colors.accent, backgroundColor:'transparent',
        yAxisID:'y1', tension:0.3 }}
    ]
  }},
  options: {{
    responsive:true, maintainAspectRatio:false,
    scales: {{
      y: {{ position:'left', ticks:{{ callback: v => 'R'+(v/1e6).toFixed(0)+'M' }} }},
      y1: {{ position:'right', grid:{{ drawOnChartArea:false }}, ticks:{{ callback: v => (v/1e3).toFixed(0)+'k' }} }}
    }}
  }}
}});
</script>

</body></html>
"""

OUT = 'takealot_pitch.html'
with open(OUT, 'w') as f:
  f.write(html)

print()
print(f'Wrote: {OUT}')
print('Open in browser and screenshot each section into slides.')
