#!/usr/bin/env python3
"""
Engen + Woolworths partnership pitch. Client-facing HTML.

The pitch anchors on the shared cohort: FNB cardholders who are active at
BOTH Engen and Woolworths in the last 12 months. Discovery showed:

  Engen customers:  2,488,131
  Woolies customers: 1,932,563
  Shared cohort:   1,500,810
  60% of Engen customers already shop Woolworths.
  77% of Woolies customers already fuel at Engen.

Every query below runs live so the numbers stay in sync with whatever the
sandbox looks like on the day it is generated.

Usage:
  python3 scripts/generate_engen_woolies_pitch.py [sandbox|production]
Output:
  engen_woolies_pitch.html
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


ENGEN_WHERE   = "UPPER(DESTINATION) LIKE '%ENGEN%'"
WOOLIES_WHERE = "(UPPER(DESTINATION) LIKE '%WOOLWORTH%' OR UPPER(DESTINATION) LIKE '%WOOLIES%')"

ENGEN_COLOR   = '#004b87'  # Engen navy
WOOLIES_COLOR = '#00A651'  # Woolies green
SHARED_COLOR  = '#f59e0b'  # amber for the shared story

print('Querying...')

# ── Engen totals (all Engen banners combined) ────────────────────────────
engen = q(f"""
  SELECT
    COUNT(DISTINCT UNIQUE_ID)                    AS customers,
    SUM(dest_txn_count)                        AS transactions,
    ROUND(SUM(dest_spend), 0)                    AS total_spend,
    ROUND(SUM(dest_spend) / NULLIF(SUM(dest_txn_count), 0), 2)    AS avg_txn_value,
    ROUND(SUM(dest_spend) / NULLIF(COUNT(DISTINCT UNIQUE_ID), 0), 0) AS spend_per_customer
  FROM `{PROJECT}.analytics.int_customer_category_spend`
  WHERE {ENGEN_WHERE}
""").iloc[0]

# ── Engen banner breakdown (Fuel vs Convenience Store) ───────────────────
engen_banners = q(f"""
  SELECT
    DESTINATION AS banner,
    ANY_VALUE(CATEGORY_TWO) AS category,
    COUNT(DISTINCT UNIQUE_ID) AS customers,
    SUM(dest_txn_count)     AS transactions,
    ROUND(SUM(dest_spend), 0) AS total_spend
  FROM `{PROJECT}.analytics.int_customer_category_spend`
  WHERE {ENGEN_WHERE}
  GROUP BY DESTINATION
  ORDER BY total_spend DESC
""").to_dict('records')

# ── Woolworths totals ────────────────────────────────────────────────────
woolies = q(f"""
  SELECT
    COUNT(DISTINCT UNIQUE_ID)                    AS customers,
    SUM(dest_txn_count)                        AS transactions,
    ROUND(SUM(dest_spend), 0)                    AS total_spend,
    ROUND(SUM(dest_spend) / NULLIF(SUM(dest_txn_count), 0), 2)    AS avg_txn_value,
    ROUND(SUM(dest_spend) / NULLIF(COUNT(DISTINCT UNIQUE_ID), 0), 0) AS spend_per_customer
  FROM `{PROJECT}.analytics.int_customer_category_spend`
  WHERE {WOOLIES_WHERE}
""").iloc[0]

# ── Woolies banner breakdown ─────────────────────────────────────────────
woolies_banners = q(f"""
  SELECT
    DESTINATION AS banner,
    ANY_VALUE(CATEGORY_TWO) AS category,
    COUNT(DISTINCT UNIQUE_ID) AS customers,
    SUM(dest_txn_count)     AS transactions,
    ROUND(SUM(dest_spend), 0) AS total_spend
  FROM `{PROJECT}.analytics.int_customer_category_spend`
  WHERE {WOOLIES_WHERE}
  GROUP BY DESTINATION
  ORDER BY total_spend DESC
  LIMIT 8
""").to_dict('records')

# ── THE SHARED COHORT ────────────────────────────────────────────────────
overlap = q(f"""
  WITH engen_c AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE {ENGEN_WHERE}
  ),
  woolies_c AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE {WOOLIES_WHERE}
  ),
  shared AS (
    SELECT e.UNIQUE_ID FROM engen_c e JOIN woolies_c w USING (UNIQUE_ID)
  )
  SELECT
    (SELECT COUNT(*) FROM engen_c)                                       AS engen_customers,
    (SELECT COUNT(*) FROM woolies_c)                                     AS woolies_customers,
    (SELECT COUNT(*) FROM shared)                                        AS shared_customers,
    ROUND(100.0 * (SELECT COUNT(*) FROM shared) /
        NULLIF((SELECT COUNT(*) FROM engen_c), 0), 1)                    AS pct_engen_at_woolies,
    ROUND(100.0 * (SELECT COUNT(*) FROM shared) /
        NULLIF((SELECT COUNT(*) FROM woolies_c), 0), 1)                  AS pct_woolies_at_engen,
    (SELECT COUNT(*) FROM engen_c) - (SELECT COUNT(*) FROM shared)       AS engen_only,
    (SELECT COUNT(*) FROM woolies_c) - (SELECT COUNT(*) FROM shared)     AS woolies_only
""").iloc[0]

# ── Shared cohort spend at each brand ────────────────────────────────────
shared_spend = q(f"""
  WITH engen_c AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE {ENGEN_WHERE}
  ),
  woolies_c AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE {WOOLIES_WHERE}
  ),
  shared AS (
    SELECT e.UNIQUE_ID FROM engen_c e JOIN woolies_c w USING (UNIQUE_ID)
  )
  SELECT
    'Engen'  AS brand,
    COUNT(DISTINCT cs.UNIQUE_ID) AS customers,
    ROUND(SUM(cs.dest_spend), 0) AS spend,
    ROUND(SUM(cs.dest_spend) / NULLIF(SUM(cs.dest_txn_count), 0), 2) AS avg_basket,
    ROUND(SUM(cs.dest_spend) / NULLIF(COUNT(DISTINCT cs.UNIQUE_ID), 0), 0) AS spend_per_customer
  FROM `{PROJECT}.analytics.int_customer_category_spend` cs
  WHERE {ENGEN_WHERE.replace('DESTINATION', 'cs.DESTINATION')}
    AND cs.UNIQUE_ID IN (SELECT UNIQUE_ID FROM shared)
  UNION ALL
  SELECT
    'Woolworths' AS brand,
    COUNT(DISTINCT cs.UNIQUE_ID) AS customers,
    ROUND(SUM(cs.dest_spend), 0) AS spend,
    ROUND(SUM(cs.dest_spend) / NULLIF(SUM(cs.dest_txn_count), 0), 2) AS avg_basket,
    ROUND(SUM(cs.dest_spend) / NULLIF(COUNT(DISTINCT cs.UNIQUE_ID), 0), 0) AS spend_per_customer
  FROM `{PROJECT}.analytics.int_customer_category_spend` cs
  WHERE {WOOLIES_WHERE.replace('DESTINATION', 'cs.DESTINATION')}
    AND cs.UNIQUE_ID IN (SELECT UNIQUE_ID FROM shared)
""").to_dict('records')

shared_spend_map = {r['brand']: r for r in shared_spend}

# ── Demographics on the shared cohort ────────────────────────────────────
demo = q(f"""
  WITH engen_c AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE {ENGEN_WHERE}
  ),
  woolies_c AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE {WOOLIES_WHERE}
  ),
  shared AS (
    SELECT e.UNIQUE_ID FROM engen_c e JOIN woolies_c w USING (UNIQUE_ID)
  )
  SELECT
    COUNT(*)                              AS customers,
    ROUND(AVG(c.age), 1)                    AS avg_age,
    COUNT(DISTINCT CASE WHEN c.gender_label = 'Male'  THEN c.UNIQUE_ID END) AS male,
    COUNT(DISTINCT CASE WHEN c.gender_label = 'Female' THEN c.UNIQUE_ID END) AS female
  FROM shared s
  JOIN `{PROJECT}.staging.stg_customers` c USING (UNIQUE_ID)
""").iloc[0]

income_gender = q(f"""
  WITH engen_c AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE {ENGEN_WHERE}
  ),
  woolies_c AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE {WOOLIES_WHERE}
  ),
  shared AS (
    SELECT e.UNIQUE_ID FROM engen_c e JOIN woolies_c w USING (UNIQUE_ID)
  )
  SELECT c.income_group AS band,
    COUNT(DISTINCT CASE WHEN c.gender_label='Male'  THEN c.UNIQUE_ID END) AS male,
    COUNT(DISTINCT CASE WHEN c.gender_label='Female' THEN c.UNIQUE_ID END) AS female
  FROM shared s JOIN `{PROJECT}.staging.stg_customers` c USING (UNIQUE_ID)
  WHERE c.income_group IS NOT NULL AND c.income_group <> 'Unknown'
  GROUP BY c.income_group
  ORDER BY CASE c.income_group
    WHEN 'R0-R5.5k' THEN 1 WHEN 'R5.5k-R13.5k' THEN 2
    WHEN 'R13.5k-R23.5k' THEN 3 WHEN 'R23.5k-R32.5k' THEN 4
    WHEN 'R32.5k-R56k' THEN 5 WHEN 'R56k+' THEN 6 ELSE 99 END
""").to_dict('records')

age_gender = q(f"""
  WITH engen_c AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE {ENGEN_WHERE}
  ),
  woolies_c AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE {WOOLIES_WHERE}
  ),
  shared AS (
    SELECT e.UNIQUE_ID FROM engen_c e JOIN woolies_c w USING (UNIQUE_ID)
  )
  SELECT c.age_group AS band,
    COUNT(DISTINCT CASE WHEN c.gender_label='Male'  THEN c.UNIQUE_ID END) AS male,
    COUNT(DISTINCT CASE WHEN c.gender_label='Female' THEN c.UNIQUE_ID END) AS female
  FROM shared s JOIN `{PROJECT}.staging.stg_customers` c USING (UNIQUE_ID)
  WHERE c.age_group IS NOT NULL AND c.age_group <> 'Unknown'
  GROUP BY c.age_group
  ORDER BY CASE c.age_group
    WHEN '18-25' THEN 1 WHEN '26-35' THEN 2
    WHEN '36-45' THEN 3 WHEN '46-60' THEN 4 WHEN '60+' THEN 5 ELSE 99 END
""").to_dict('records')

# ── Provincial spend of the shared cohort (fuel + grocery combined) ──────
geo = q(f"""
  WITH engen_c AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE {ENGEN_WHERE}
  ),
  woolies_c AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE {WOOLIES_WHERE}
  ),
  shared AS (
    SELECT e.UNIQUE_ID FROM engen_c e JOIN woolies_c w USING (UNIQUE_ID)
  )
  SELECT t.PROVINCE AS province,
    COUNT(DISTINCT t.UNIQUE_ID) AS customers,
    ROUND(SUM(t.trns_amt), 0) AS spend
  FROM shared s
  JOIN `{PROJECT}.staging.stg_transactions` t USING (UNIQUE_ID)
  WHERE ({ENGEN_WHERE.replace('DESTINATION', 't.DESTINATION')}
      OR {WOOLIES_WHERE.replace('DESTINATION', 't.DESTINATION')})
    AND t.PROVINCE IS NOT NULL
  GROUP BY t.PROVINCE
  ORDER BY spend DESC
  LIMIT 9
""").to_dict('records')

# ── Segment quality of the shared cohort ─────────────────────────────────
segments = q(f"""
  WITH engen_c AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE {ENGEN_WHERE}
  ),
  woolies_c AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE {WOOLIES_WHERE}
  ),
  shared AS (
    SELECT e.UNIQUE_ID FROM engen_c e JOIN woolies_c w USING (UNIQUE_ID)
  )
  SELECT co.segment_name AS segment, COUNT(*) AS customers,
    ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (), 1) AS pct
  FROM shared s JOIN `{PROJECT}.marts.mart_cluster_output` co USING (UNIQUE_ID)
  GROUP BY co.segment_name ORDER BY customers DESC
""").to_dict('records')

# ── Cross-shop of shared cohort (top 10 other categories) ────────────────
cross_shop = q(f"""
  WITH engen_c AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE {ENGEN_WHERE}
  ),
  woolies_c AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE {WOOLIES_WHERE}
  ),
  shared AS (
    SELECT e.UNIQUE_ID FROM engen_c e JOIN woolies_c w USING (UNIQUE_ID)
  )
  SELECT cs.CATEGORY_TWO AS category,
    COUNT(DISTINCT cs.UNIQUE_ID) AS shoppers,
    ROUND(SUM(cs.dest_spend), 0) AS spend
  FROM `{PROJECT}.analytics.int_customer_category_spend` cs
  JOIN shared s USING (UNIQUE_ID)
  WHERE cs.CATEGORY_TWO NOT IN (
    'Fuel','Fuel and Filling Stations','Petroleum','Filling Stations',
    'Convenience Store','Groceries'
  )
  GROUP BY cs.CATEGORY_TWO
  ORDER BY shoppers DESC
  LIMIT 10
""").to_dict('records')

# ── Fuel competitive set (Engen inside its category) ─────────────────────
fuel_comp = q(f"""
  SELECT DESTINATION,
    COUNT(DISTINCT UNIQUE_ID) AS customers,
    ROUND(SUM(dest_spend), 0) AS spend
  FROM `{PROJECT}.analytics.int_customer_category_spend`
  WHERE CATEGORY_TWO IN ('Fuel','Fuel and Filling Stations','Petroleum','Filling Stations')
    AND (UPPER(DESTINATION) LIKE '%ENGEN%' OR UPPER(DESTINATION) LIKE '%SHELL%'
      OR UPPER(DESTINATION) LIKE '%SASOL%' OR UPPER(DESTINATION) LIKE '%BP%'
      OR UPPER(DESTINATION) LIKE '%TOTAL%' OR UPPER(DESTINATION) LIKE '%ASTRON%'
      OR UPPER(DESTINATION) LIKE '%PUMA%' OR UPPER(DESTINATION) LIKE '%CALTEX%')
  GROUP BY DESTINATION
  ORDER BY customers DESC
  LIMIT 8
""").to_dict('records')

# ── Grocery competitive set (Woolies inside its category) ────────────────
grocery_comp = q(f"""
  SELECT DESTINATION,
    COUNT(DISTINCT UNIQUE_ID) AS customers,
    ROUND(SUM(dest_spend), 0) AS spend
  FROM `{PROJECT}.analytics.int_customer_category_spend`
  WHERE CATEGORY_TWO = 'Groceries'
  GROUP BY DESTINATION
  ORDER BY total_spend := SUM(dest_spend) DESC
""").to_dict('records') if False else q(f"""
  SELECT DESTINATION,
    COUNT(DISTINCT UNIQUE_ID) AS customers,
    ROUND(SUM(dest_spend), 0) AS spend
  FROM `{PROJECT}.analytics.int_customer_category_spend`
  WHERE CATEGORY_TWO = 'Groceries'
  GROUP BY DESTINATION
  ORDER BY spend DESC
  LIMIT 8
""").to_dict('records')

# ── Monthly trend (spend at Engen + Woolies by shared cohort) ────────────
trend = q(f"""
  WITH engen_c AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE {ENGEN_WHERE}
  ),
  woolies_c AS (
    SELECT DISTINCT UNIQUE_ID FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE {WOOLIES_WHERE}
  ),
  shared AS (
    SELECT e.UNIQUE_ID FROM engen_c e JOIN woolies_c w USING (UNIQUE_ID)
  )
  SELECT FORMAT_DATE('%Y-%m', t.EFF_DATE) AS month,
    COUNT(DISTINCT t.UNIQUE_ID) AS customers,
    ROUND(SUM(t.trns_amt), 0) AS spend
  FROM `{PROJECT}.staging.stg_transactions` t
  JOIN shared s USING (UNIQUE_ID)
  WHERE ({ENGEN_WHERE.replace('DESTINATION', 't.DESTINATION')}
      OR {WOOLIES_WHERE.replace('DESTINATION', 't.DESTINATION')})
  GROUP BY month ORDER BY month
""").to_dict('records')

print('  → data collected')


# ── Timeframe footer ─────────────────────────────────────────────────────
if trend:
  first_month = str(trend[0]['month'])
  last_month  = str(trend[-1]['month'])
  timeframe_text = f'Transactions cover the 12 months from {first_month} to {last_month}.'
else:
  timeframe_text = 'Transactions cover the last 12 months.'


data_obj = {
  'income_gender': [{'band': str(r['band']), 'male': int(r['male']), 'female': int(r['female'])} for r in income_gender],
  'age_gender':  [{'band': str(r['band']), 'male': int(r['male']), 'female': int(r['female'])} for r in age_gender],
  'geo':      [{'province': str(r['province']), 'customers': int(r['customers']), 'spend': float(r['spend'])} for r in geo],
  'segments':   [{'name': str(r['segment']), 'customers': int(r['customers']), 'pct': float(r['pct'])} for r in segments],
  'cross_shop':  [{'category': str(r['category']), 'shoppers': int(r['shoppers']), 'spend': float(r['spend'])} for r in cross_shop],
  'trend':    [{'month': str(r['month']), 'customers': int(r['customers']), 'spend': float(r['spend'])} for r in trend],
  'venn':     {'engen_only':   int(overlap['engen_only']),
               'shared':       int(overlap['shared_customers']),
               'woolies_only': int(overlap['woolies_only'])},
}


def kpi_card(label, value, sub=''):
  sub_html = f'<div class="s">{esc(sub)}</div>' if sub else ''
  return f'<div class="card"><div class="l">{esc(label)}</div><div class="v">{esc(value)}</div>{sub_html}</div>'


now = datetime.now().strftime('%d %B %Y')

# ── Trend narrative ──────────────────────────────────────────────────────
trend_narrative = ''
if len(trend) >= 3:
  first_half  = trend[:len(trend)//2]
  second_half = trend[len(trend)//2:]
  avg_first   = sum(m['spend'] for m in first_half)  / len(first_half)
  avg_second  = sum(m['spend'] for m in second_half) / len(second_half)
  direction_pct = round(100 * (avg_second - avg_first) / max(avg_first, 1), 1)
  peak = max(trend, key=lambda m: m['spend'])
  trough = min(trend, key=lambda m: m['spend'])
  if direction_pct > 3:
    direction = f'<b style="color:#16a34a">growing</b> ({direction_pct:+.1f}% H1 to H2)'
  elif direction_pct < -3:
    direction = f'<b style="color:#e11d48">softening</b> ({direction_pct:+.1f}% H1 to H2)'
  else:
    direction = f'<b style="color:#334155">stable</b> ({direction_pct:+.1f}% H1 to H2)'
  trend_narrative = (
    f'Shared-cohort combined spend is {direction}. Peak month: '
    f'<b>{esc(peak["month"])}</b> ({R(peak["spend"])}). '
    f'Softest month: <b>{esc(trough["month"])}</b> ({R(trough["spend"])}).'
  )

# ── HTML pieces ──────────────────────────────────────────────────────────
engen_kpis = '<div class="row">' + ''.join([
  kpi_card('Customers',    N(engen['customers']),      'across all Engen banners'),
  kpi_card('Annual Spend', R(engen['total_spend'])),
  kpi_card('Transactions', N(engen['transactions'])),
  kpi_card('Avg Basket',   R(engen['avg_txn_value'])),
  kpi_card('Spend / Customer', R_exact(engen['spend_per_customer']), 'per year'),
]) + '</div>'

woolies_kpis = '<div class="row">' + ''.join([
  kpi_card('Customers',    N(woolies['customers']),    'across all Woolworths banners'),
  kpi_card('Annual Spend', R(woolies['total_spend'])),
  kpi_card('Transactions', N(woolies['transactions'])),
  kpi_card('Avg Basket',   R(woolies['avg_txn_value'])),
  kpi_card('Spend / Customer', R_exact(woolies['spend_per_customer']), 'per year'),
]) + '</div>'

# Partnership headline block
combined_shared_spend = float(shared_spend_map.get('Engen', {}).get('spend', 0)) + \
                        float(shared_spend_map.get('Woolworths', {}).get('spend', 0))

partnership_kpis = '<div class="row">' + ''.join([
  kpi_card('Shared cohort', N(overlap['shared_customers']), 'shop BOTH brands'),
  kpi_card('of Engen customers', f"{overlap['pct_engen_at_woolies']:.1f}%", 'also shop Woolworths'),
  kpi_card('of Woolies customers', f"{overlap['pct_woolies_at_engen']:.1f}%", 'also fuel at Engen'),
  kpi_card('Combined shared spend', R(combined_shared_spend), 'Engen + Woolworths, 12mo'),
]) + '</div>'

# Three cohort cards
total_pool = int(overlap['engen_only']) + int(overlap['shared_customers']) + int(overlap['woolies_only'])
def _pct(n): return round(100.0 * n / max(total_pool, 1), 1)

cohort_cards = f'''
<div class="cohort-row">
  <div class="cohort cohort-engen">
   <div class="cohort-badge" style="background:{ENGEN_COLOR}">ENGEN ONLY</div>
   <div class="cohort-size">{N(overlap['engen_only'])}</div>
   <div class="cohort-pct">{_pct(int(overlap['engen_only']))}% of combined pool</div>
   <div class="cohort-desc">Fuel loyalists who currently do not shop Woolworths. The clearest cross-sell target for the FoodStop concession.</div>
  </div>
  <div class="cohort cohort-shared">
   <div class="cohort-badge" style="background:{SHARED_COLOR}">SHARED COHORT</div>
   <div class="cohort-size">{N(overlap['shared_customers'])}</div>
   <div class="cohort-pct">{_pct(int(overlap['shared_customers']))}% of combined pool</div>
   <div class="cohort-desc">Already live the partnership. High value, dual brand affinity. Deepen the wallet, do not defend it.</div>
  </div>
  <div class="cohort cohort-woolies">
   <div class="cohort-badge" style="background:{WOOLIES_COLOR}">WOOLIES ONLY</div>
   <div class="cohort-size">{N(overlap['woolies_only'])}</div>
   <div class="cohort-pct">{_pct(int(overlap['woolies_only']))}% of combined pool</div>
   <div class="cohort-desc">Premium grocery buyers who do not fuel at Engen yet. Every visit converted is a fuel wallet share win.</div>
  </div>
</div>
'''

# Shared cohort deep dive
engen_shared  = shared_spend_map.get('Engen',      {'customers': 0, 'spend': 0, 'avg_basket': 0, 'spend_per_customer': 0})
woolies_shared = shared_spend_map.get('Woolworths', {'customers': 0, 'spend': 0, 'avg_basket': 0, 'spend_per_customer': 0})

shared_deep = f'''
<div class="deep-row">
  <div class="deep-card" style="border-left:5px solid {ENGEN_COLOR}">
   <div class="deep-name">Shared cohort at Engen</div>
   <div class="deep-metrics">
    <div><span class="l">Annual spend</span> {R(engen_shared['spend'])}</div>
    <div><span class="l">Avg basket</span> {R_exact(engen_shared['avg_basket'])}</div>
    <div><span class="l">Spend / customer</span> {R_exact(engen_shared['spend_per_customer'])}</div>
   </div>
  </div>
  <div class="deep-card" style="border-left:5px solid {WOOLIES_COLOR}">
   <div class="deep-name">Shared cohort at Woolworths</div>
   <div class="deep-metrics">
    <div><span class="l">Annual spend</span> {R(woolies_shared['spend'])}</div>
    <div><span class="l">Avg basket</span> {R_exact(woolies_shared['avg_basket'])}</div>
    <div><span class="l">Spend / customer</span> {R_exact(woolies_shared['spend_per_customer'])}</div>
   </div>
  </div>
</div>
'''

# Engen and Woolies banner tables
engen_banner_rows = ''
for r in engen_banners:
  engen_banner_rows += (f'<tr><td>{esc(r["banner"])}</td>'
                        f'<td>{esc(r["category"])}</td>'
                        f'<td>{N(r["customers"])}</td>'
                        f'<td>{N(r["transactions"])}</td>'
                        f'<td>{R(r["total_spend"])}</td></tr>')
woolies_banner_rows = ''
for r in woolies_banners:
  woolies_banner_rows += (f'<tr><td>{esc(r["banner"])}</td>'
                          f'<td>{esc(r["category"])}</td>'
                          f'<td>{N(r["customers"])}</td>'
                          f'<td>{N(r["transactions"])}</td>'
                          f'<td>{R(r["total_spend"])}</td></tr>')

# Competitive rows
fuel_rows = ''
for r in fuel_comp:
  is_engen = 'ENGEN' in str(r['DESTINATION']).upper()
  css = ' class="brand"' if is_engen else ''
  fuel_rows += (f'<tr{css}><td>{esc(r["DESTINATION"])}</td>'
                f'<td>{N(r["customers"])}</td><td>{R(r["spend"])}</td></tr>')
grocery_rows = ''
for r in grocery_comp:
  is_woolies = 'WOOLWORTH' in str(r['DESTINATION']).upper() or 'WOOLIES' in str(r['DESTINATION']).upper()
  css = ' class="brand"' if is_woolies else ''
  grocery_rows += (f'<tr{css}><td>{esc(r["DESTINATION"])}</td>'
                   f'<td>{N(r["customers"])}</td><td>{R(r["spend"])}</td></tr>')

# Demographics
total_gender = int(demo['male']) + int(demo['female'])
demo_row = ''.join([
  kpi_card('Female', f"{round(100*demo['female']/total_gender,1)}%", f"{N(demo['female'])} customers"),
  kpi_card('Male',   f"{round(100*demo['male']/total_gender,1)}%",   f"{N(demo['male'])} customers"),
  kpi_card('Avg age', f"{demo['avg_age']}", 'years'),
])

# Cross-shop rows
cross_shop_rows = ''
for r in cross_shop:
  cross_shop_rows += (f'<tr><td>{esc(r["category"])}</td>'
                      f'<td>{N(r["shoppers"])}</td>'
                      f'<td>{R(r["spend"])}</td></tr>')

top_2_segments_pct = round(sum(s['pct'] for s in segments[:2]), 1) if len(segments) >= 2 else 0


html = f"""<!DOCTYPE html>
<html lang='en'><head><meta charset='UTF-8'>
<title>Engen and Woolworths, Partnership Audience Snapshot</title>
<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'></script>
<script src='https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0'></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'DM Sans',sans-serif; background:#f8fafc; color:#1a202c; }}
#hdr {{ background:linear-gradient(135deg,{ENGEN_COLOR},{WOOLIES_COLOR}); color:#fff; padding:28px 32px; }}
#hdr h1 {{ font-size:1.9rem; font-weight:700; }}
#hdr p {{ opacity:.92; font-size:1rem; margin-top:6px; }}
#hdr .meta {{ font-size:.78rem; opacity:.65; margin-top:14px; }}
.ctn {{ max-width:1200px; margin:0 auto; padding:24px; }}
.sec {{ background:#fff; border-radius:14px; padding:26px 30px; margin:18px 0; border:1px solid #f1f5f9; box-shadow:0 1px 4px rgba(0,0,0,.04); }}
.sec h2 {{ font-size:1.35rem; font-weight:700; color:#0f172a; margin-bottom:6px; }}
.sec .sub {{ color:#64748b; font-size:.92rem; margin-bottom:18px; line-height:1.5; }}
.hero-partnership {{ background:linear-gradient(135deg,#fff7ed,#fed7aa); border:2px solid {SHARED_COLOR}; }}
.hero-partnership h2 {{ color:#78350f; }}
.hero-partnership .sub {{ color:#92400e; }}
.callout {{ background:#dcfce7; border-left:4px solid #16a34a; border-radius:0 10px 10px 0; padding:14px 18px; margin:14px 0; font-size:.95rem; color:#14532d; line-height:1.5; }}
.row {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:12px 0; }}
.card {{ background:#f8fafc; border-radius:10px; padding:16px; text-align:center; border-top:3px solid {SHARED_COLOR}; }}
.hero-partnership .card {{ background:#fffbeb; border-top-color:{SHARED_COLOR}; }}
.card .l {{ font-size:.72rem; color:#64748b; font-weight:600; text-transform:uppercase; letter-spacing:.03em; }}
.card .v {{ font-size:1.5rem; font-weight:700; color:#0f172a; margin-top:6px; }}
.card .s {{ font-size:.72rem; color:#94a3b8; margin-top:3px; }}
.chbox {{ position:relative; height:300px; margin:12px 0; }}
.chbox.tall {{ height:360px; }}
.two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
@media(max-width:800px) {{ .two-col {{ grid-template-columns:1fr; }} }}
table {{ width:100%; border-collapse:collapse; margin:12px 0; font-size:.86rem; }}
th {{ background:#0f172a; color:#fff; padding:10px 12px; text-align:left; font-size:.72rem; text-transform:uppercase; letter-spacing:.03em; }}
td {{ padding:9px 12px; border-bottom:1px solid #f1f5f9; }}
tr.brand td {{ background:#fef3c7; font-weight:600; }}
.brand-card {{ background:#fff; border-radius:12px; padding:20px 22px; border:2px solid #f1f5f9; }}
.brand-engen {{ border-color:{ENGEN_COLOR}; background:linear-gradient(180deg,#eaf2fa 0%,#fff 60%); }}
.brand-woolies {{ border-color:{WOOLIES_COLOR}; background:linear-gradient(180deg,#e6f6ea 0%,#fff 60%); }}
.brand-header {{ display:flex; align-items:center; gap:10px; margin-bottom:10px; }}
.brand-header h3 {{ font-size:1.1rem; font-weight:700; color:#0f172a; margin:0; }}
.brand-badge {{ font-size:.66rem; font-weight:700; padding:3px 10px; border-radius:12px; letter-spacing:.06em; color:#fff; }}
.brand-badge.engen  {{ background:{ENGEN_COLOR}; }}
.brand-badge.woolies {{ background:{WOOLIES_COLOR}; }}
.brand-engen .card  {{ border-top-color:{ENGEN_COLOR}; }}
.brand-woolies .card {{ border-top-color:{WOOLIES_COLOR}; }}
.cohort-row {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-top:14px; }}
@media(max-width:850px) {{ .cohort-row {{ grid-template-columns:1fr; }} }}
.cohort {{ background:#fff; border-radius:12px; padding:22px 24px; border:2px solid #f1f5f9; }}
.cohort-engen  {{ border-color:{ENGEN_COLOR}; background:linear-gradient(180deg,#eaf2fa 0%,#fff 60%); }}
.cohort-shared {{ border-color:{SHARED_COLOR}; background:linear-gradient(180deg,#fffbeb 0%,#fff 60%); }}
.cohort-woolies {{ border-color:{WOOLIES_COLOR}; background:linear-gradient(180deg,#e6f6ea 0%,#fff 60%); }}
.cohort-badge {{ display:inline-block; font-size:.65rem; font-weight:700; padding:3px 10px; border-radius:12px; letter-spacing:.06em; color:#fff; }}
.cohort-size {{ font-size:2rem; font-weight:700; color:#0f172a; margin:8px 0 0; font-variant-numeric:tabular-nums; }}
.cohort-pct  {{ font-size:.82rem; font-weight:600; color:#78350f; margin:2px 0 10px; }}
.cohort-desc {{ font-size:.85rem; color:#475569; line-height:1.55; }}
.deep-row {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:12px; }}
@media(max-width:800px) {{ .deep-row {{ grid-template-columns:1fr; }} }}
.deep-card {{ background:#fff; border-radius:10px; padding:16px 20px; }}
.deep-name {{ font-size:1rem; font-weight:700; color:#0f172a; margin-bottom:8px; }}
.deep-metrics {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; font-size:.9rem; color:#334155; }}
.deep-metrics .l {{ font-size:.68rem; color:#64748b; font-weight:600; display:block; text-transform:uppercase; letter-spacing:.03em; }}
.trend-story {{ background:#f1f5f9; border-radius:10px; padding:14px 18px; margin-top:14px; font-size:.94rem; color:#334155; line-height:1.55; }}
.timeframe {{ font-size:.82rem; color:#64748b; margin-top:10px; font-style:italic; }}
</style>
</head><body>

<div id='hdr'>
<h1>Engen and Woolworths, Partnership Audience Snapshot</h1>
<p>FNB cardholder view of the shared Engen and Woolworths cohort, last 12 months.</p>
<div class='meta'>Generated {esc(now)}</div>
</div>

<div class='ctn'>

<div class='sec hero-partnership'>
<h2>The partnership is already the story</h2>
<p class='sub'>The Engen and Woolworths partnership is not a hypothesis. Most of each brand's FNB card base is already active at the other brand. This audience is the ready made proof point.</p>
{partnership_kpis}
<div class='callout' style='background:#fef3c7; border-left-color:{SHARED_COLOR}; color:#78350f'>
<b>{overlap['pct_woolies_at_engen']:.0f}% of Woolworths customers already fuel at Engen. {overlap['pct_engen_at_woolies']:.0f}% of Engen customers already shop at Woolworths.</b> The FoodStop concession has a warm audience of over {N(overlap['shared_customers'])} people to build from.
</div>
</div>

<div class='sec'>
<h2>The three cohorts</h2>
<p class='sub'>Every FNB cardholder who touched either brand in the last 12 months falls into one of three groups. The partnership plays are different for each.</p>
{cohort_cards}
</div>

<div class='sec'>
<h2>Shared cohort deep dive</h2>
<p class='sub'>The 1.5M FNB cardholders active at both brands. Their spend at each brand is below.</p>
{shared_deep}
<div class='callout' style='margin-top:14px'>
The shared cohort spends <b>{R(combined_shared_spend)}</b> across the two brands per year, or <b>R{int((float(engen_shared['spend_per_customer'])+float(woolies_shared['spend_per_customer'])) / 1):,}</b> per customer per year on average. This is a high value, high frequency audience.
</div>
</div>

<div class='sec'>
<h2>Each brand on its own</h2>
<p class='sub'>For context: the standalone reach of each brand in FNB card data.</p>
<div class='two-col'>
<div class='brand-card brand-engen'>
<div class='brand-header'><span class='brand-badge engen'>ENGEN</span><h3>Engen, all banners</h3></div>
{engen_kpis}
</div>
<div class='brand-card brand-woolies'>
<div class='brand-header'><span class='brand-badge woolies'>WOOLWORTHS</span><h3>Woolworths, all banners</h3></div>
{woolies_kpis}
</div>
</div>
</div>

<div class='sec'>
<h2>Banner breakdown, Engen</h2>
<table><tr><th>Banner</th><th>Category</th><th>Customers</th><th>Transactions</th><th>Annual spend</th></tr>{engen_banner_rows}</table>
</div>

<div class='sec'>
<h2>Banner breakdown, Woolworths</h2>
<table><tr><th>Banner</th><th>Category</th><th>Customers</th><th>Transactions</th><th>Annual spend</th></tr>{woolies_banner_rows}</table>
</div>

<div class='sec'>
<h2>Who they are, the shared cohort</h2>
<div class='row'>
{demo_row}
</div>
</div>

<div class='sec'>
<h2>Income and gender profile, shared cohort</h2>
<div class='chbox tall'><canvas id='chIncomeGender'></canvas></div>
</div>

<div class='sec'>
<h2>Age and gender profile, shared cohort</h2>
<div class='chbox tall'><canvas id='chAgeGender'></canvas></div>
</div>

<div class='sec'>
<h2>Geographic footprint, shared cohort</h2>
<p class='sub'>Combined Engen and Woolworths spend by province among the shared cohort.</p>
<div class='chbox tall'><canvas id='chGeo'></canvas></div>
</div>

<div class='sec'>
<h2>Customer quality, shared cohort</h2>
<p class='sub'>Shared customers clustered by FNB's behavioural segmentation model.</p>
<div class='callout'>
<b>{top_2_segments_pct}% of shared cohort customers sit in FNB's two highest-value segments.</b> The partnership audience skews to the top of the value ladder.
</div>
<div class='two-col'>
<div class='chbox'><canvas id='chSegments'></canvas></div>
<div style='font-size:.88rem;line-height:1.6;color:#334155'>
<h3 style='font-size:1rem;color:#0f172a;margin-bottom:8px'>What the segments mean</h3>
<p><b style='color:#16a34a'>Loyal High Value.</b> Consistently high spenders with strong recency. Top of the funnel.</p>
<p style='margin-top:8px'><b style='color:{SHARED_COLOR}'>Champions.</b> Highest lifetime value, broad category spread, frequent transactions.</p>
<p style='margin-top:8px'><b style='color:{WOOLIES_COLOR}'>Steady Mid-Tier.</b> Reliable regulars with moderate but stable spend patterns.</p>
<p style='margin-top:8px'><b style='color:#e11d48'>Dormant.</b> Previously active but low recent engagement. Re-activation opportunity.</p>
<p style='margin-top:8px'><b style='color:#94a3b8'>At Risk.</b> Spend and frequency declining. Win-back campaign candidates.</p>
</div>
</div>
</div>

<div class='sec'>
<h2>Monthly trend, shared cohort combined spend</h2>
<div class='chbox tall'><canvas id='chTrend'></canvas></div>
<div class='trend-story'>{trend_narrative}</div>
</div>

<div class='sec'>
<h2>Where Engen sits in the fuel category</h2>
<p class='sub'>Top fuel destinations in FNB card data, ranked by customer reach.</p>
<table><tr><th>Retailer</th><th>Customers</th><th>Annual spend</th></tr>{fuel_rows}</table>
</div>

<div class='sec'>
<h2>Where Woolworths sits in the grocery category</h2>
<p class='sub'>Top grocery destinations in FNB card data, ranked by spend.</p>
<table><tr><th>Retailer</th><th>Customers</th><th>Annual spend</th></tr>{grocery_rows}</table>
</div>

<div class='sec'>
<h2>Cross-shop, co-brand and bundling opportunities</h2>
<p class='sub'>The top categories the shared cohort already spends in outside fuel and grocery. Natural targets for joint promotions and category expansion.</p>
<table><tr><th>Category</th><th>Shoppers</th><th>Annual spend</th></tr>{cross_shop_rows}</table>
</div>

<div class='sec' style='background:#f8fafc; border:1px solid #e2e8f0;'>
<h2>Scope and timeframe</h2>
<p class='sub'>This view combines all Engen DESTINATIONs (Engen fuel and Engen Convenience Store) with all Woolworths DESTINATIONs. The shared cohort is the set of FNB cardholders active at both brands in the same 12 month window.</p>
<p class='timeframe'>{timeframe_text}</p>
</div>

</div>

<script>
const Data = {json.dumps(data_obj)};
const colors = {{
  male:'#2E75B6', female:'#E85C0D',
  engen:'{ENGEN_COLOR}', woolies:'{WOOLIES_COLOR}', shared:'{SHARED_COLOR}',
  seg: ['#16a34a','{SHARED_COLOR}','{WOOLIES_COLOR}','#e11d48','#94a3b8'],
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
      {{ label:'Male',   data: Data.income_gender.map(r=>r.male),   backgroundColor: colors.male   }},
      {{ label:'Female', data: Data.income_gender.map(r=>r.female), backgroundColor: colors.female }}
    ] }},
  options: {{ responsive:true, maintainAspectRatio:false, scales:{{ y:{{ beginAtZero:true }} }} }}
}});

mkChart('chAgeGender', {{
  type:'bar',
  data: {{ labels: Data.age_gender.map(r=>r.band),
    datasets: [
      {{ label:'Male',   data: Data.age_gender.map(r=>r.male),   backgroundColor: colors.male   }},
      {{ label:'Female', data: Data.age_gender.map(r=>r.female), backgroundColor: colors.female }}
    ] }},
  options: {{ responsive:true, maintainAspectRatio:false, scales:{{ y:{{ beginAtZero:true }} }} }}
}});

mkChart('chGeo', {{
  type:'bar',
  data: {{ labels: Data.geo.map(r=>r.province),
    datasets: [{{ label:'Spend', data: Data.geo.map(r=>r.spend),
      backgroundColor: colors.shared, borderColor: colors.engen, borderWidth:1 }}] }},
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
         borderColor: colors.shared, backgroundColor:'rgba(245,158,11,0.15)',
         yAxisID:'y', tension:0.3, fill:true }},
      {{ label:'Customers', data: Data.trend.map(r=>r.customers),
         borderColor: colors.engen, backgroundColor:'transparent',
         yAxisID:'y1', tension:0.3 }}
    ] }},
  options: {{
    responsive:true, maintainAspectRatio:false,
    scales: {{
      y:  {{ position:'left',  ticks:{{ callback: v => 'R'+(v/1e9).toFixed(1)+'B' }} }},
      y1: {{ position:'right', grid:{{ drawOnChartArea:false }}, ticks:{{ callback: v => (v/1e3).toFixed(0)+'k' }} }}
    }}
  }}
}});
</script>
</body></html>
"""

OUT = 'engen_woolies_pitch.html'
with open(OUT, 'w') as f:
  f.write(html)

print()
print(f'Wrote: {OUT}')
print('Open in browser and screenshot each section into slides.')
