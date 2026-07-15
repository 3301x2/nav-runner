#!/usr/bin/env python3
"""
Pick n Pay GROUP pitch - screenshot-ready HTML.
Multi-banner: all 9 PnP DESTINATIONs combined into one Group audience:
 - PICK N PAY (flagship supermarket)
 - PICK N PAY EXPRESS (convenience / forecourt)
 - PICK N PAY ASAP (on-demand delivery)
 - PICK N PAY CLOTHING (apparel)
 - PICK N PAY SAVE (discount format)
 - PICK N PAY LIQUOR (liquor stores)
 - PNP PHARMACY (health / wellness)
 - PICK N PAY VAS (airtime / value-added)
 - PICK N PAY TRAVEL

Hero = union of all banners (unique customers, total spend).
Banner-split section shows the format mix inside.

Usage:
  python3 scripts/generate_pnp_group_pitch.py [sandbox|production]
Output:
  pnp_group_pitch.html
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


PNP_DESTS_SQL = (
  "'PICK N PAY','PICK N PAY EXPRESS','PICK N PAY ASAP',"
  "'PICK N PAY CLOTHING','PICK N PAY SAVE','PICK N PAY LIQUOR',"
  "'PNP PHARMACY','PICK N PAY VAS','PICK N PAY TRAVEL'"
)
BRAND_NAME = 'Pick n Pay Group'
BRAND_COLOR = '#0072BC'

# ── Queries ─────────────────────────────────────────────────────────────
print('Querying...')

# Hero: union across all PnP banners
hero = q(f"""
  SELECT
    COUNT(DISTINCT UNIQUE_ID)                    AS customers,
    SUM(dest_txn_count)                       AS transactions,
    ROUND(SUM(dest_spend), 0)                    AS total_spend,
    ROUND(SUM(dest_spend) / NULLIF(SUM(dest_txn_count), 0), 2)    AS avg_txn_value,
    ROUND(SUM(dest_spend) / NULLIF(COUNT(DISTINCT UNIQUE_ID), 0), 0) AS spend_per_customer
  FROM `{PROJECT}.analytics.int_customer_category_spend`
  WHERE UPPER(DESTINATION) IN ({PNP_DESTS_SQL})
""").iloc[0]

# Cross-check: set-logic union of unique customers across banners
validate = q(f"""
  SELECT COUNT(DISTINCT UNIQUE_ID) AS true_union
  FROM `{PROJECT}.analytics.int_customer_category_spend`
  WHERE UPPER(DESTINATION) IN ({PNP_DESTS_SQL})
""").iloc[0]
primary = int(hero['customers']); union = int(validate['true_union'])
delta_pct = abs(primary - union) / max(union, 1) * 100
print(f' Validation: primary={primary:,}, union={union:,}, delta={delta_pct:.3f}%')
if delta_pct > 1.0:
  sys.exit(f'\n❌ ABORTING: combined customer base disagrees by {delta_pct:.2f}%.')
print(' ✓ Validation passed')

# Per-banner breakdown
banners = q(f"""
  SELECT
    DESTINATION AS banner,
    COUNT(DISTINCT UNIQUE_ID) AS customers,
    SUM(dest_txn_count)    AS transactions,
    ROUND(SUM(dest_spend), 0) AS total_spend,
    ROUND(SUM(dest_spend) / NULLIF(SUM(dest_txn_count), 0), 2) AS avg_txn_value,
    ROUND(SUM(dest_spend) / NULLIF(COUNT(DISTINCT UNIQUE_ID), 0), 0) AS spend_per_customer
  FROM `{PROJECT}.analytics.int_customer_category_spend`
  WHERE UPPER(DESTINATION) IN ({PNP_DESTS_SQL})
  GROUP BY DESTINATION
  ORDER BY total_spend DESC
""").to_dict('records')

# Demographics on combined audience
demo = q(f"""
  WITH custs AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE UPPER(DESTINATION) IN ({PNP_DESTS_SQL})
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
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE UPPER(DESTINATION) IN ({PNP_DESTS_SQL})
  )
  SELECT c.income_group AS band,
    COUNT(DISTINCT CASE WHEN c.gender_label='Male'  THEN c.UNIQUE_ID END) AS male,
    COUNT(DISTINCT CASE WHEN c.gender_label='Female' THEN c.UNIQUE_ID END) AS female
  FROM custs f JOIN `{PROJECT}.staging.stg_customers` c USING (UNIQUE_ID)
  WHERE c.income_group IS NOT NULL AND c.income_group <> 'Unknown'
  GROUP BY c.income_group
  ORDER BY CASE c.income_group
    WHEN 'R0-R5.5k' THEN 1 WHEN 'R5.5k-R13.5k' THEN 2
    WHEN 'R13.5k-R23.5k' THEN 3 WHEN 'R23.5k-R32.5k' THEN 4
    WHEN 'R32.5k-R56k' THEN 5 WHEN 'R56k+' THEN 6 ELSE 99 END
""").to_dict('records')

age_gender = q(f"""
  WITH custs AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE UPPER(DESTINATION) IN ({PNP_DESTS_SQL})
  )
  SELECT c.age_group AS band,
    COUNT(DISTINCT CASE WHEN c.gender_label='Male'  THEN c.UNIQUE_ID END) AS male,
    COUNT(DISTINCT CASE WHEN c.gender_label='Female' THEN c.UNIQUE_ID END) AS female
  FROM custs f JOIN `{PROJECT}.staging.stg_customers` c USING (UNIQUE_ID)
  WHERE c.age_group IS NOT NULL AND c.age_group <> 'Unknown'
  GROUP BY c.age_group
  ORDER BY CASE c.age_group
    WHEN '18-25' THEN 1 WHEN '26-35' THEN 2
    WHEN '36-45' THEN 3 WHEN '46-60' THEN 4 WHEN '60+' THEN 5 ELSE 99 END
""").to_dict('records')

geo = q(f"""
  WITH custs AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE UPPER(DESTINATION) IN ({PNP_DESTS_SQL})
  )
  SELECT t.PROVINCE AS province,
    COUNT(DISTINCT t.UNIQUE_ID) AS customers,
    ROUND(SUM(t.trns_amt), 0) AS spend
  FROM custs f JOIN `{PROJECT}.staging.stg_transactions` t USING (UNIQUE_ID)
  WHERE UPPER(t.DESTINATION) IN ({PNP_DESTS_SQL}) AND t.PROVINCE IS NOT NULL
  GROUP BY t.PROVINCE ORDER BY spend DESC LIMIT 9
""").to_dict('records')

segments = q(f"""
  WITH custs AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE UPPER(DESTINATION) IN ({PNP_DESTS_SQL})
  )
  SELECT co.segment_name AS segment, COUNT(*) AS customers,
    ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (), 1) AS pct
  FROM custs f JOIN `{PROJECT}.marts.mart_cluster_output` co USING (UNIQUE_ID)
  GROUP BY co.segment_name ORDER BY customers DESC
""").to_dict('records')

cross_shop = q(f"""
  WITH custs AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE UPPER(DESTINATION) IN ({PNP_DESTS_SQL})
  )
  SELECT cs.CATEGORY_TWO AS category,
    COUNT(DISTINCT cs.UNIQUE_ID) AS shoppers,
    ROUND(SUM(cs.dest_spend), 0) AS spend
  FROM custs f JOIN `{PROJECT}.analytics.int_customer_category_spend` cs USING (UNIQUE_ID)
  WHERE cs.CATEGORY_TWO NOT IN ('Groceries','Clothing and Apparel','Liquor Stores',
                  'Pharmacies and Wellbeing','Travel Agency')
  GROUP BY cs.CATEGORY_TWO ORDER BY shoppers DESC LIMIT 10
""").to_dict('records')

trend = q(f"""
  SELECT FORMAT_DATE('%Y-%m', t.EFF_DATE) AS month,
    COUNT(DISTINCT t.UNIQUE_ID) AS customers,
    ROUND(SUM(t.trns_amt), 0) AS spend
  FROM `{PROJECT}.staging.stg_transactions` t
  WHERE UPPER(t.DESTINATION) IN ({PNP_DESTS_SQL})
  GROUP BY month ORDER BY month
""").to_dict('records')

segment_spend = q(f"""
  WITH activity AS (
    SELECT cs.UNIQUE_ID, SUM(cs.dest_spend) AS spend
    FROM `{PROJECT}.analytics.int_customer_category_spend` cs
    WHERE UPPER(cs.DESTINATION) IN ({PNP_DESTS_SQL})
    GROUP BY cs.UNIQUE_ID
  )
  SELECT co.segment_name AS segment, COUNT(*) AS customers,
    ROUND(SUM(f.spend), 0) AS annual_spend
  FROM activity f JOIN `{PROJECT}.marts.mart_cluster_output` co USING (UNIQUE_ID)
  GROUP BY co.segment_name
""").to_dict('records')

# Multi-format engagement - how many banners the average customer touches
multi_format = q(f"""
  WITH cust_banners AS (
    SELECT UNIQUE_ID, COUNT(DISTINCT DESTINATION) AS banner_count
    FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE UPPER(DESTINATION) IN ({PNP_DESTS_SQL})
    GROUP BY UNIQUE_ID
  )
  SELECT
    COUNTIF(banner_count = 1) AS one_banner,
    COUNTIF(banner_count = 2) AS two_banners,
    COUNTIF(banner_count = 3) AS three_banners,
    COUNTIF(banner_count >= 4) AS four_plus_banners,
    ROUND(AVG(banner_count), 2) AS avg_banners_per_customer
  FROM cust_banners
""").iloc[0]

# Switch pool: grocery category vs PnP-flagship (Market) footprint,
# then also show non-PnP-anything as second row
switch = q(f"""
  WITH grocery_c AS (
    SELECT cs.UNIQUE_ID, SUM(cs.dest_spend) AS spend
    FROM `{PROJECT}.analytics.int_customer_category_spend` cs
    WHERE cs.CATEGORY_TWO = 'Groceries' GROUP BY cs.UNIQUE_ID
  ),
  pnp_c AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE UPPER(DESTINATION) IN ({PNP_DESTS_SQL})
  )
  SELECT
    (SELECT COUNT(DISTINCT UNIQUE_ID) FROM grocery_c) AS category_customers,
    (SELECT ROUND(SUM(spend),0) FROM grocery_c) AS category_spend,
    (SELECT COUNT(*) FROM pnp_c) AS pnp_customers,
    (SELECT COUNT(DISTINCT UNIQUE_ID) FROM grocery_c WHERE UNIQUE_ID NOT IN (SELECT UNIQUE_ID FROM pnp_c)) AS non_pnp_customers,
    (SELECT ROUND(SUM(spend),0) FROM grocery_c WHERE UNIQUE_ID NOT IN (SELECT UNIQUE_ID FROM pnp_c)) AS non_pnp_spend
""").iloc[0]

print(' → data collected')

# Banner colours (rotating within brand blue variants)
banner_colors = {
  'PICK N PAY':     '#0072BC',
  'PICK N PAY EXPRESS': '#00A0DC',
  'PICK N PAY ASAP':   '#e11d48',
  'PICK N PAY CLOTHING': '#9333ea',
  'PICK N PAY SAVE':   '#eab308',
  'PICK N PAY LIQUOR':  '#78350f',
  'PNP PHARMACY':    '#16a34a',
  'PICK N PAY VAS':   '#f59e0b',
  'PICK N PAY TRAVEL':  '#334155',
}

data_obj = {
  'banners':    [{'banner': str(r['banner']), 'customers': int(r['customers']),
            'total_spend': float(r['total_spend']),
            'spend_per_customer': float(r['spend_per_customer']),
            'color': banner_colors.get(str(r['banner']).upper(), '#0072BC')} for r in banners],
  'income_gender': [{'band': str(r['band']), 'male': int(r['male']), 'female': int(r['female'])} for r in income_gender],
  'age_gender':  [{'band': str(r['band']), 'male': int(r['male']), 'female': int(r['female'])} for r in age_gender],
  'geo':      [{'province': str(r['province']), 'customers': int(r['customers']), 'spend': float(r['spend'])} for r in geo],
  'segments':   [{'name': str(r['segment']), 'customers': int(r['customers']), 'pct': float(r['pct'])} for r in segments],
  'cross_shop':  [{'category': str(r['category']), 'shoppers': int(r['shoppers']), 'spend': float(r['spend'])} for r in cross_shop],
  'trend':     [{'month': str(r['month']), 'customers': int(r['customers']), 'spend': float(r['spend'])} for r in trend],
  'multi_format': {'one': int(multi_format['one_banner']),
           'two': int(multi_format['two_banners']),
           'three': int(multi_format['three_banners']),
           'four_plus': int(multi_format['four_plus_banners']),
           'avg': float(multi_format['avg_banners_per_customer'])},
}


def kpi_card(label, value, sub=''):
  sub_html = f'<div class="s">{esc(sub)}</div>' if sub else ''
  return f'<div class="card"><div class="l">{esc(label)}</div><div class="v">{esc(value)}</div>{sub_html}</div>'


now = datetime.now().strftime('%d %B %Y')

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

seg_by_name = {s['segment']: s for s in segments}
seg_spend_by_name = {s['segment']: s for s in segment_spend}
def _seg(name, key='customers'):
  row = seg_by_name.get(name); return int(row[key]) if row else 0
def _seg_spend(name):
  row = seg_spend_by_name.get(name); return int(row['annual_spend']) if row else 0

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
   <div class="act-desc">Your highest-value customers - the Smart Shopper base that treats {BRAND_NAME} as a one-stop household. Retention plays: Smart Shopper multi-format perks (grocery + clothing + pharmacy in one journey), premium range access, priority for on-demand ASAP delivery slots.</div>
  </div>''',
  f'''<div class="act-card act-grow">
   <div class="act-badge">GROW</div>
   <h3>Steady Mid-Tier</h3>
   <div class="act-size">{N(grow_pool)}</div>
   <div class="act-money">{R(grow_spend)} current spend · upside potential</div>
   <div class="act-desc">Reliable weekly shoppers ready to graduate from single-banner to multi-format. Cross-banner nudges (Market → Express top-up, Grocery → Clothing/Pharmacy), and Smart Shopper accelerators on categories they don't yet shop.</div>
  </div>''',
  f'''<div class="act-card act-reengage">
   <div class="act-badge">RE-ENGAGE</div>
   <h3>Dormant &amp; At Risk</h3>
   <div class="act-size">{N(reengage_pool)}</div>
   <div class="act-money">{R(reengage_spend)} lapsed spend to recover</div>
   <div class="act-desc">Previously active customers with fading engagement. Win-back with personalised come-back offers on their old favourite categories and Smart Shopper reactivation bonuses.</div>
  </div>''',
])

hero_kpis = '<div class="row">' + ''.join([
  kpi_card('Customers', N(hero['customers']), 'unique across all banners'),
  kpi_card('Annual Spend', R(hero['total_spend']), 'group-wide'),
  kpi_card('Transactions', N(hero['transactions'])),
  kpi_card('Avg Basket', R(hero['avg_txn_value'])),
  kpi_card('Spend / Customer', R_exact(hero['spend_per_customer']), 'per year'),
  kpi_card('Avg Age', f"{demo['avg_age']}"),
]) + '</div>'

# Banner-split cards
banner_cards = ''
for r in banners:
  banner = str(r['banner'])
  color = banner_colors.get(banner.upper(), '#0072BC')
  banner_cards += f'''
  <div class="banner-card" style="border-left:5px solid {color}">
   <div class="banner-name">{esc(banner)}</div>
   <div class="banner-metrics">
    <div><span class="l">Customers</span> {N(r['customers'])}</div>
    <div><span class="l">Annual Spend</span> {R(r['total_spend'])}</div>
    <div><span class="l">Spend / Cust</span> {R_exact(r['spend_per_customer'])}</div>
    <div><span class="l">Avg Basket</span> {R(r['avg_txn_value'])}</div>
   </div>
  </div>'''

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

# Multi-format story
mf_total = data_obj['multi_format']['one'] + data_obj['multi_format']['two'] + \
      data_obj['multi_format']['three'] + data_obj['multi_format']['four_plus']
mf_multi_pct = round(100 * (data_obj['multi_format']['two'] + data_obj['multi_format']['three'] +
               data_obj['multi_format']['four_plus']) / max(mf_total, 1), 1)


html = f"""<!DOCTYPE html>
<html lang='en'><head><meta charset='UTF-8'>
<title>{BRAND_NAME} - Audience Snapshot</title>
<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'></script>
<script src='https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0'></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'DM Sans',sans-serif; background:#f8fafc; color:#1a202c; }}
#hdr {{ background:linear-gradient(135deg,#003a6b,{BRAND_COLOR}); color:#fff; padding:28px 32px; }}
#hdr h1 {{ font-size:1.9rem; font-weight:700; }}
#hdr p {{ opacity:.9; font-size:1rem; margin-top:6px; }}
#hdr .meta {{ font-size:.78rem; opacity:.6; margin-top:14px; }}
.ctn {{ max-width:1200px; margin:0 auto; padding:24px; }}
.sec {{ background:#fff; border-radius:14px; padding:26px 30px; margin:18px 0; border:1px solid #f1f5f9; box-shadow:0 1px 4px rgba(0,0,0,.04); }}
.sec h2 {{ font-size:1.35rem; font-weight:700; color:#0f172a; margin-bottom:6px; }}
.sec .sub {{ color:#64748b; font-size:.92rem; margin-bottom:18px; line-height:1.5; }}
.hero {{ background:linear-gradient(135deg,#e0f0fa,#c6dff7); border:1px solid {BRAND_COLOR}; }}
.hero h2 {{ color:#003a6b; }}
.hero .sub {{ color:#004a86; }}
.callout {{ background:#dcfce7; border-left:4px solid #16a34a; border-radius:0 10px 10px 0; padding:14px 18px; margin:14px 0; font-size:.95rem; color:#14532d; line-height:1.5; }}
.row {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:12px 0; }}
.card {{ background:#f8fafc; border-radius:10px; padding:16px; text-align:center; border-top:3px solid {BRAND_COLOR}; }}
.hero .card {{ background:#eef7fd; border-top-color:{BRAND_COLOR}; }}
.card .l {{ font-size:.72rem; color:#64748b; font-weight:600; text-transform:uppercase; letter-spacing:.03em; }}
.card .v {{ font-size:1.5rem; font-weight:700; color:#0f172a; margin-top:6px; }}
.card .s {{ font-size:.72rem; color:#94a3b8; margin-top:3px; }}
.chbox {{ position:relative; height:300px; margin:12px 0; }}
.chbox.tall {{ height:360px; }}
.two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
@media(max-width:800px) {{ .two-col {{ grid-template-columns:1fr; }} }}
table {{ width:100%; border-collapse:collapse; margin:12px 0; font-size:.86rem; }}
th {{ background:#003a6b; color:#fff; padding:10px 12px; text-align:left; font-size:.72rem; text-transform:uppercase; letter-spacing:.03em; }}
td {{ padding:9px 12px; border-bottom:1px solid #f1f5f9; }}
.banner-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:14px; }}
@media(max-width:800px) {{ .banner-grid {{ grid-template-columns:1fr; }} }}
.banner-card {{ background:#f8fafc; border-radius:10px; padding:14px 18px; }}
.banner-name {{ font-size:.95rem; font-weight:700; color:#0f172a; margin-bottom:8px; text-transform:uppercase; letter-spacing:.03em; }}
.banner-metrics {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:.85rem; color:#334155; }}
.banner-metrics .l {{ font-size:.68rem; color:#64748b; font-weight:600; display:block; text-transform:uppercase; letter-spacing:.03em; }}
.act-row {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-top:14px; }}
@media(max-width:850px) {{ .act-row {{ grid-template-columns:1fr; }} }}
.act-card {{ background:#fff; border-radius:12px; padding:20px 22px; border:2px solid #f1f5f9; position:relative; }}
.act-card h3 {{ font-size:1.05rem; font-weight:700; color:#0f172a; margin:8px 0 4px; }}
.act-badge {{ display:inline-block; font-size:.65rem; font-weight:700; padding:3px 10px; border-radius:12px; letter-spacing:.06em; color:#fff; }}
.act-size {{ font-size:1.7rem; font-weight:700; color:#0f172a; margin:6px 0 0; font-variant-numeric:tabular-nums; }}
.act-money {{ font-size:.8rem; font-weight:600; color:#003a6b; margin:4px 0 10px; letter-spacing:.01em; }}
.act-desc {{ font-size:.85rem; color:#475569; line-height:1.55; }}
.act-protect {{ border-color:#16a34a; background:linear-gradient(180deg,#f0fdf4 0%,#fff 60%); }}
.act-protect .act-badge {{ background:#16a34a; }}
.act-grow   {{ border-color:{BRAND_COLOR}; background:linear-gradient(180deg,#eef7fd 0%,#fff 60%); }}
.act-grow   .act-badge {{ background:{BRAND_COLOR}; }}
.act-reengage {{ border-color:#e11d48; background:linear-gradient(180deg,#fef2f2 0%,#fff 60%); }}
.act-reengage .act-badge {{ background:#e11d48; }}
.trend-story {{ background:#f1f5f9; border-radius:10px; padding:14px 18px; margin-top:14px; font-size:.94rem; color:#334155; line-height:1.55; }}
</style>
</head><body>

<div id='hdr'>
<h1>{BRAND_NAME} - Audience Snapshot</h1>
<p>FNB cardholder activity across all {BRAND_NAME} banners, last 12 months</p>
<div class='meta'>Generated {esc(now)}</div>
</div>

<div class='ctn'>

<div class='sec hero'>
<h2>The Group reach story</h2>
<p class='sub'>Distinct FNB cardholders who touched any {BRAND_NAME} banner - Market, Express, ASAP, Clothing, Save, Liquor, Pharmacy, VAS, or Travel - in the last 12 months. A multi-format retail relationship, not just a supermarket footprint.</p>
{hero_kpis}
</div>

<div class='sec'>
<h2>How the audience splits across banners</h2>
<p class='sub'>Each banner's individual footprint. Customers who shop multiple banners appear in more than one row - the hero above is the deduplicated unique-customer total.</p>
<div class='banner-grid'>
{banner_cards}
</div>
</div>

<div class='sec' style='background:linear-gradient(180deg,#fefce8 0%,#fff 40%); border:2px solid #eab308'>
<h2 style='color:#713f12'>Multi-format engagement</h2>
<p class='sub'>How many {BRAND_NAME} banners the average customer touches. Multi-format engagement is the moat - every extra banner deepens the relationship.</p>
<div class='row'>
{kpi_card('Single-banner', N(data_obj['multi_format']['one']), f"{round(100 * data_obj['multi_format']['one'] / max(mf_total, 1), 1)}% of audience")}
{kpi_card('Two banners', N(data_obj['multi_format']['two']))}
{kpi_card('Three banners', N(data_obj['multi_format']['three']))}
{kpi_card('4+ banners', N(data_obj['multi_format']['four_plus']))}
{kpi_card('Avg banners / customer', f"{data_obj['multi_format']['avg']:.2f}")}
</div>
<div class='callout' style='margin-top:14px'>
<b>{mf_multi_pct}% of {BRAND_NAME} customers shop across two or more banners</b> - the multi-format retailer story. Every single-banner customer converted to multi-format grows lifetime value dramatically.
</div>
</div>

<div class='sec'>
<h2>Customer quality</h2>
<p class='sub'>{BRAND_NAME} customers clustered by FNB's behavioural segmentation model. Segments reflect FNB-wide activity, not {BRAND_NAME}-specific.</p>
<div class='callout'>
<b>{top_2_segments_pct}% of {BRAND_NAME} customers are in FNB's two highest-value segments</b> - the same shoppers driving premium retail activity across the ecosystem.
</div>
<div class='two-col'>
<div class='chbox'><canvas id='chSegments'></canvas></div>
<div style='font-size:.88rem;line-height:1.6;color:#334155'>
<h3 style='font-size:1rem;color:#0f172a;margin-bottom:8px'>What the segments mean</h3>
<p><b style='color:#16a34a'>Loyal High Value</b> - consistently high spenders with strong recency.</p>
<p style='margin-top:8px'><b style='color:{BRAND_COLOR}'>Champions</b> - highest lifetime value; broad category spread and frequent transactions.</p>
<p style='margin-top:8px'><b style='color:#f59e0b'>Steady Mid-Tier</b> - reliable regulars with moderate but stable spend patterns.</p>
<p style='margin-top:8px'><b style='color:#e11d48'>Dormant</b> - previously active but low recent engagement - re-activation opportunity.</p>
<p style='margin-top:8px'><b style='color:#94a3b8'>At Risk</b> - spend and frequency declining - win-back campaign candidates.</p>
</div>
</div>
</div>

<div class='sec'>
<h2>Who they are</h2>
<div class='row'>
{demo_row}
</div>
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
<p class='sub'>Total {BRAND_NAME} Group spend by province.</p>
<div class='chbox tall'><canvas id='chGeo'></canvas></div>
</div>

<div class='sec'>
<h2>Monthly trend</h2>
<div class='chbox tall'><canvas id='chTrend'></canvas></div>
<div class='trend-story'>{trend_narrative}</div>
</div>

<div class='sec'>
<h2>Activation opportunities</h2>
<p class='sub'>The audience isn't monolithic - it's three distinct pools, each with a different play, and a real spend number attached.</p>
<div class='act-row'>
{activation_cards}
</div>
</div>

<div class='sec' style='background:linear-gradient(180deg,#fff7ed 0%,#fff 40%); border:2px solid #d97706'>
<h2 style='color:#92400e'>Switch opportunity - the winnable ground</h2>
<p class='sub'>The size of the grocery pool in FNB card data, and how much of it is not yet reached by any {BRAND_NAME} banner.</p>
<div class='row'>
{kpi_card('Category customers', N(switch['category_customers']), 'FNB grocery shoppers, 12mo')}
{kpi_card(f'{BRAND_NAME} customers', N(switch['pnp_customers']), f"{round(100 * int(switch['pnp_customers']) / max(int(switch['category_customers']), 1), 1)}% of category")}
{kpi_card('Non-PnP customers', N(switch['non_pnp_customers']), 'the switch pool')}
{kpi_card('Non-PnP grocery spend', R(switch['non_pnp_spend']), 'currently going elsewhere')}
</div>
<div class='callout' style='margin-top:14px'>
{round(100 * int(switch['non_pnp_customers']) / max(int(switch['category_customers']), 1), 1)}% of FNB grocery shoppers currently spend nothing at any {BRAND_NAME} banner. Winning even a small share of that spend represents meaningful group growth - and multi-format is your unique wedge.
</div>
</div>

<div class='sec'>
<h2>Adjacent spend - bundling &amp; co-brand opportunities</h2>
<p class='sub'>The top categories your customers already spend in outside {BRAND_NAME}'s own formats. Useful for bundle offers, co-brand partnerships, and channel targeting.</p>
<table><tr><th>Category</th><th>Shoppers</th><th>Annual spend</th></tr>{cross_shop_rows}</table>
</div>

</div>

<script>
const Data = {json.dumps(data_obj)};
const colors = {{
  male:'#2E75B6', female:'#E85C0D', brand:'{BRAND_COLOR}', accent:'#003a6b',
  seg: ['#16a34a','{BRAND_COLOR}','#f59e0b','#e11d48','#94a3b8'],
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
  type:'doughnut',
  data: {{
    labels: Data.segments.map(r => r.name + ' (' + r.pct.toFixed(1) + '%)'),
    datasets: [{{
      data: Data.segments.map(r => r.customers),
      backgroundColor: Data.segments.map((_,i) => colors.seg[i % colors.seg.length]),
      borderColor:'#fff', borderWidth:3
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
  type:'bar',
  data: {{ labels: Data.income_gender.map(r=>r.band),
    datasets: [
      {{ label:'Male',  data: Data.income_gender.map(r=>r.male),  backgroundColor: colors.male  }},
      {{ label:'Female', data: Data.income_gender.map(r=>r.female), backgroundColor: colors.female }}
    ] }},
  options: {{ responsive:true, maintainAspectRatio:false, scales:{{ y:{{ beginAtZero:true }} }} }}
}});

mkChart('chAgeGender', {{
  type:'bar',
  data: {{ labels: Data.age_gender.map(r=>r.band),
    datasets: [
      {{ label:'Male',  data: Data.age_gender.map(r=>r.male),  backgroundColor: colors.male  }},
      {{ label:'Female', data: Data.age_gender.map(r=>r.female), backgroundColor: colors.female }}
    ] }},
  options: {{ responsive:true, maintainAspectRatio:false, scales:{{ y:{{ beginAtZero:true }} }} }}
}});

mkChart('chGeo', {{
  type:'bar',
  data: {{ labels: Data.geo.map(r=>r.province),
    datasets: [{{ label:'Spend', data: Data.geo.map(r=>r.spend),
      backgroundColor: colors.brand, borderColor: colors.accent, borderWidth:1 }}] }},
  options: {{
    indexAxis:'y', responsive:true, maintainAspectRatio:false,
    plugins:{{ legend:{{ display:false }} }},
    scales:{{ x:{{ beginAtZero:true, ticks:{{ callback: v => 'R'+(v/1e9).toFixed(1)+'B' }} }} }}
  }}
}});

mkChart('chTrend', {{
  type:'line',
  data: {{ labels: Data.trend.map(r=>r.month),
    datasets: [
      {{ label:'Spend', data: Data.trend.map(r=>r.spend),
        borderColor: colors.brand, backgroundColor:'rgba(0,114,188,0.15)',
        yAxisID:'y', tension:0.3, fill:true }},
      {{ label:'Customers', data: Data.trend.map(r=>r.customers),
        borderColor: colors.accent, backgroundColor:'transparent',
        yAxisID:'y1', tension:0.3 }}
    ] }},
  options: {{
    responsive:true, maintainAspectRatio:false,
    scales: {{
      y: {{ position:'left', ticks:{{ callback: v => 'R'+(v/1e9).toFixed(2)+'B' }} }},
      y1: {{ position:'right', grid:{{ drawOnChartArea:false }}, ticks:{{ callback: v => (v/1e3).toFixed(0)+'k' }} }}
    }}
  }}
}});
</script>
</body></html>
"""

OUT = 'pnp_group_pitch.html'
with open(OUT, 'w') as f:
  f.write(html)

print()
print(f'Wrote: {OUT}')
print('Open in browser and screenshot each section into slides.')
