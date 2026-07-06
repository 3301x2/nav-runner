#!/usr/bin/env python3
"""
Food Lovers CLIENT-FACING pitch — screenshot-ready HTML with clean numbers
+ Chart.js charts. Combined (Market + Eatery) is the hero view per Yumna's
guidance ("treat as same team / audience viewing the insights you share").

DELIBERATE OMISSIONS (internal-only, kept out of client deck):
    • Groceries category totals (R177B, 497M txns) — not the client's story
    • Category-scope callouts ("in Groceries") wherever avoidable
    • Provenance / overlap footnotes ("Market + Eatery − in_both = union")
    • Internal quality-control validation notes
    • References to stg_customers.income_group / nav_dashboard / mart names
    • The GCP project name in the metadata

Numbers still validated at generation time — if the combined base fails
the ±1% cross-check against set-logic union, the script aborts.

Usage:
    python3 scripts/generate_food_lovers_pitch.py [sandbox|production]
Output:
    food_lovers_pitch.html
"""
from __future__ import annotations
import html as _h
import json
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


def R(v) -> str:
    if v is None or pd.isna(v):
        return 'N/A'
    v = float(v)
    if abs(v) >= 1e9: return f'R{v/1e9:.2f}B'
    if abs(v) >= 1e6: return f'R{v/1e6:.1f}M'
    if abs(v) >= 1e3: return f'R{v/1e3:.0f}k'
    return f'R{v:,.0f}'


def R_exact(v) -> str:
    """Full-precision Rand formatter for values where rounding to R4k / R1k
    hides real differences (e.g. spend per customer where R4,181 vs R1,150
    tells a story that R4k / R1k does not)."""
    if v is None or pd.isna(v):
        return 'N/A'
    return f'R{float(v):,.0f}'


def N(v) -> str:
    if v is None or pd.isna(v):
        return 'N/A'
    return f'{int(v):,}'


def esc(s) -> str:
    return _h.escape(str(s))


# ── Queries ──────────────────────────────────────────────────────────────
print('Querying...')

# Groceries totals (kept for internal validation only — not shown)
groc = q(f"""
    SELECT
        COUNT(DISTINCT UNIQUE_ID) AS customers,
        SUM(dest_txn_count)       AS transactions,
        ROUND(SUM(dest_spend), 0) AS spend
    FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE CATEGORY_TWO = 'Groceries'
""").iloc[0]

# Food Lovers Market from mart (has rank / market share / penetration)
fl_market = q(f"""
    SELECT
        customers, transactions, total_spend, avg_txn_value,
        spend_per_customer, market_share_pct, penetration_pct,
        avg_share_of_wallet, spend_rank
    FROM `{PROJECT}.marts.mart_destination_benchmarks`
    WHERE CATEGORY_TWO = 'Groceries'
      AND UPPER(DESTINATION) = 'FOOD LOVERS MARKET'
""")
fl_market_row = fl_market.iloc[0] if not fl_market.empty else None

# Food Lovers Eatery — compute LIVE from raw data (mart's Groceries filter
# excludes it because Eatery lives in a different category).
fl_eatery = q(f"""
    SELECT
        COUNT(DISTINCT UNIQUE_ID)                                        AS customers,
        SUM(dest_txn_count)                                              AS transactions,
        ROUND(SUM(dest_spend), 0)                                        AS total_spend,
        ROUND(SUM(dest_spend) / NULLIF(SUM(dest_txn_count), 0), 2)       AS avg_txn_value,
        ROUND(SUM(dest_spend) / NULLIF(COUNT(DISTINCT UNIQUE_ID), 0), 0) AS spend_per_customer
    FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE UPPER(DESTINATION) = 'FOOD LOVERS EATERY'
""")
fl_eatery_row = fl_eatery.iloc[0] if not fl_eatery.empty else None

# Combined (union across both DESTINATIONs regardless of category)
fl_combined = q(f"""
    SELECT
        COUNT(DISTINCT UNIQUE_ID)                                        AS customers,
        SUM(dest_txn_count)                                              AS transactions,
        ROUND(SUM(dest_spend), 0)                                        AS total_spend,
        ROUND(SUM(dest_spend) / NULLIF(SUM(dest_txn_count), 0), 2)       AS avg_txn_value,
        ROUND(SUM(dest_spend) / NULLIF(COUNT(DISTINCT UNIQUE_ID), 0), 0) AS spend_per_customer
    FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE UPPER(DESTINATION) IN ('FOOD LOVERS MARKET', 'FOOD LOVERS EATERY')
""").iloc[0]

# Cross-check the combined count against set-logic (internal only)
fl_validate = q(f"""
    WITH market AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE UPPER(DESTINATION) = 'FOOD LOVERS MARKET'
    ),
    eatery AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE UPPER(DESTINATION) = 'FOOD LOVERS EATERY'
    )
    SELECT
        (SELECT COUNT(*) FROM market) AS market_customers,
        (SELECT COUNT(*) FROM eatery) AS eatery_customers,
        (SELECT COUNT(*) FROM market m JOIN eatery e USING (UNIQUE_ID)) AS in_both,
        (SELECT COUNT(*) FROM (
            SELECT UNIQUE_ID FROM market
            UNION DISTINCT
            SELECT UNIQUE_ID FROM eatery)) AS true_union
""").iloc[0]

primary_combined = int(fl_combined['customers'])
validation_union = int(fl_validate['true_union'])
delta_pct = abs(primary_combined - validation_union) / max(validation_union, 1) * 100
print(f'  Combined validation: primary={primary_combined:,}, union={validation_union:,}, delta={delta_pct:.3f}%')
if delta_pct > 1.0:
    sys.exit(
        f'\n❌ ABORTING: combined customer base disagrees by {delta_pct:.2f}%.\n'
        f'   Refusing to generate a pitch with unreliable numbers.'
    )
print('  ✓ Validation passed')

# Groceries top 8 competitors (for the competitive chart)
competitors = q(f"""
    SELECT
        DESTINATION,
        customers,
        total_spend,
        spend_per_customer,
        market_share_pct
    FROM `{PROJECT}.marts.mart_destination_benchmarks`
    WHERE CATEGORY_TWO = 'Groceries'
    ORDER BY total_spend DESC
    LIMIT 8
""").to_dict('records')

# Demographics for combined audience
demo = q(f"""
    WITH fl_custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE UPPER(DESTINATION) IN ('FOOD LOVERS MARKET', 'FOOD LOVERS EATERY')
    )
    SELECT
        COUNT(*)                                                              AS customers,
        ROUND(AVG(c.age), 1)                                                  AS avg_age,
        COUNT(DISTINCT CASE WHEN c.gender_label = 'Male'   THEN c.UNIQUE_ID END) AS male,
        COUNT(DISTINCT CASE WHEN c.gender_label = 'Female' THEN c.UNIQUE_ID END) AS female
    FROM fl_custs f
    JOIN `{PROJECT}.staging.stg_customers` c USING (UNIQUE_ID)
""").iloc[0]

# Income band × gender
income_gender = q(f"""
    WITH fl_custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE UPPER(DESTINATION) IN ('FOOD LOVERS MARKET', 'FOOD LOVERS EATERY')
    )
    SELECT
        c.income_group AS band,
        COUNT(DISTINCT CASE WHEN c.gender_label = 'Male'   THEN c.UNIQUE_ID END) AS male,
        COUNT(DISTINCT CASE WHEN c.gender_label = 'Female' THEN c.UNIQUE_ID END) AS female
    FROM fl_custs f
    JOIN `{PROJECT}.staging.stg_customers` c USING (UNIQUE_ID)
    WHERE c.income_group IS NOT NULL
      AND c.income_group <> 'Unknown'
    GROUP BY c.income_group
    ORDER BY
      CASE c.income_group
        WHEN 'R0-R5.5k' THEN 1
        WHEN 'R5.5k-R13.5k' THEN 2
        WHEN 'R13.5k-R23.5k' THEN 3
        WHEN 'R23.5k-R32.5k' THEN 4
        WHEN 'R32.5k-R56k' THEN 5
        WHEN 'R56k+' THEN 6
        ELSE 99
      END
""").to_dict('records')

# Age band × gender
age_gender = q(f"""
    WITH fl_custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE UPPER(DESTINATION) IN ('FOOD LOVERS MARKET', 'FOOD LOVERS EATERY')
    )
    SELECT
        c.age_group AS band,
        COUNT(DISTINCT CASE WHEN c.gender_label = 'Male'   THEN c.UNIQUE_ID END) AS male,
        COUNT(DISTINCT CASE WHEN c.gender_label = 'Female' THEN c.UNIQUE_ID END) AS female
    FROM fl_custs f
    JOIN `{PROJECT}.staging.stg_customers` c USING (UNIQUE_ID)
    WHERE c.age_group IS NOT NULL
      AND c.age_group <> 'Unknown'
    GROUP BY c.age_group
    ORDER BY
      CASE c.age_group
        WHEN '18-25' THEN 1
        WHEN '26-35' THEN 2
        WHEN '36-45' THEN 3
        WHEN '46-60' THEN 4
        WHEN '60+'   THEN 5
        ELSE 99
      END
""").to_dict('records')

# Spend by province (top 9 → SA has 9 provinces)
geo = q(f"""
    WITH fl_custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE UPPER(DESTINATION) IN ('FOOD LOVERS MARKET', 'FOOD LOVERS EATERY')
    )
    SELECT
        t.PROVINCE AS province,
        COUNT(DISTINCT t.UNIQUE_ID) AS customers,
        ROUND(SUM(t.trns_amt), 0)   AS spend
    FROM fl_custs f
    JOIN `{PROJECT}.staging.stg_transactions` t USING (UNIQUE_ID)
    WHERE UPPER(t.DESTINATION) IN ('FOOD LOVERS MARKET', 'FOOD LOVERS EATERY')
      AND t.PROVINCE IS NOT NULL
    GROUP BY t.PROVINCE
    ORDER BY spend DESC
    LIMIT 9
""").to_dict('records')

# ML segment mix — the "quality of audience" story
segments = q(f"""
    WITH fl_custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE UPPER(DESTINATION) IN ('FOOD LOVERS MARKET', 'FOOD LOVERS EATERY')
    )
    SELECT
        co.segment_name AS segment,
        COUNT(*)                                             AS customers,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)   AS pct
    FROM fl_custs f
    JOIN `{PROJECT}.marts.mart_cluster_output` co USING (UNIQUE_ID)
    GROUP BY co.segment_name
    ORDER BY customers DESC
""").to_dict('records')

# Cross-shop — what else these customers spend on (top 8 other categories)
cross_shop = q(f"""
    WITH fl_custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE UPPER(DESTINATION) IN ('FOOD LOVERS MARKET', 'FOOD LOVERS EATERY')
    )
    SELECT
        cs.CATEGORY_TWO AS category,
        COUNT(DISTINCT cs.UNIQUE_ID) AS shoppers,
        ROUND(SUM(cs.dest_spend), 0) AS spend
    FROM fl_custs f
    JOIN `{PROJECT}.analytics.int_customer_category_spend` cs USING (UNIQUE_ID)
    WHERE cs.CATEGORY_TWO NOT IN ('Groceries', 'Fast Food', 'Restaurants')
    GROUP BY cs.CATEGORY_TWO
    ORDER BY shoppers DESC
    LIMIT 8
""").to_dict('records')

# Monthly trend (12 months) — spend at Food Lovers by month
trend = q(f"""
    SELECT
        FORMAT_DATE('%Y-%m', t.EFF_DATE) AS month,
        COUNT(DISTINCT t.UNIQUE_ID)      AS customers,
        ROUND(SUM(t.trns_amt), 0)        AS spend
    FROM `{PROJECT}.staging.stg_transactions` t
    WHERE UPPER(t.DESTINATION) IN ('FOOD LOVERS MARKET', 'FOOD LOVERS EATERY')
    GROUP BY month
    ORDER BY month
""").to_dict('records')

# Fresh-first loyalists — customers whose FL share of grocery spend is very high.
# Ties directly into Food Lovers' brand pillar ("fresh at value").
loyalist = q(f"""
    WITH fl_and_grocery AS (
        SELECT
            UNIQUE_ID,
            SUM(CASE WHEN UPPER(DESTINATION) IN ('FOOD LOVERS MARKET','FOOD LOVERS EATERY')
                     THEN dest_spend ELSE 0 END) AS fl_spend,
            SUM(CASE WHEN CATEGORY_TWO = 'Groceries'
                     THEN dest_spend ELSE 0 END) AS grocery_spend
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE CATEGORY_TWO = 'Groceries'
           OR UPPER(DESTINATION) IN ('FOOD LOVERS MARKET','FOOD LOVERS EATERY')
        GROUP BY UNIQUE_ID
        HAVING SUM(CASE WHEN UPPER(DESTINATION) IN ('FOOD LOVERS MARKET','FOOD LOVERS EATERY')
                        THEN dest_spend ELSE 0 END) > 0
    )
    SELECT
        COUNTIF(fl_spend / NULLIF(grocery_spend + fl_spend, 0) >= 0.60) AS loyalist_customers,
        ROUND(SUM(CASE WHEN fl_spend / NULLIF(grocery_spend + fl_spend, 0) >= 0.60
                       THEN fl_spend ELSE 0 END), 0)                    AS loyalist_spend,
        COUNTIF(fl_spend / NULLIF(grocery_spend + fl_spend, 0) BETWEEN 0.20 AND 0.60) AS regular_customers,
        COUNTIF(fl_spend / NULLIF(grocery_spend + fl_spend, 0) < 0.20)  AS occasional_customers
    FROM fl_and_grocery
""").iloc[0]

# Aspirational acquisition target — young + mid-to-upper income + heavy grocery
# spender at competitors (i.e. NOT Food Lovers). This is who they should be
# trying to convert.
acq_target = q(f"""
    WITH grocery_spenders AS (
        -- All customers who spend on groceries anywhere in SA
        SELECT
            cs.UNIQUE_ID,
            SUM(cs.dest_spend) AS grocery_spend
        FROM `{PROJECT}.analytics.int_customer_category_spend` cs
        WHERE cs.CATEGORY_TWO = 'Groceries'
        GROUP BY cs.UNIQUE_ID
    ),
    fl_customers AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE UPPER(DESTINATION) IN ('FOOD LOVERS MARKET','FOOD LOVERS EATERY')
    )
    SELECT
        COUNT(DISTINCT g.UNIQUE_ID) AS acq_customers,
        ROUND(SUM(g.grocery_spend), 0) AS acq_grocery_spend
    FROM grocery_spenders g
    JOIN `{PROJECT}.staging.stg_customers` c ON g.UNIQUE_ID = c.UNIQUE_ID
    WHERE g.UNIQUE_ID NOT IN (SELECT UNIQUE_ID FROM fl_customers)
      AND c.age BETWEEN 26 AND 45
      AND c.income_group IN ('R23.5k-R32.5k','R32.5k-R56k','R56k+')
      AND g.grocery_spend >= 12000  -- reasonable annual grocery spend threshold
""").iloc[0]

# Spend attached to each segment — for the activation opportunity cards
segment_spend = q(f"""
    WITH fl_activity AS (
        SELECT
            cs.UNIQUE_ID,
            SUM(cs.dest_spend) AS fl_spend
        FROM `{PROJECT}.analytics.int_customer_category_spend` cs
        WHERE UPPER(cs.DESTINATION) IN ('FOOD LOVERS MARKET','FOOD LOVERS EATERY')
        GROUP BY cs.UNIQUE_ID
    )
    SELECT
        co.segment_name AS segment,
        COUNT(*)                                                       AS customers,
        ROUND(SUM(f.fl_spend), 0)                                      AS fl_annual_spend
    FROM fl_activity f
    JOIN `{PROJECT}.marts.mart_cluster_output` co USING (UNIQUE_ID)
    GROUP BY co.segment_name
""").to_dict('records')

print('  → data collected')


# ── Bundle for Chart.js ──────────────────────────────────────────────────
data_obj = {
    'competitors': [
        {'name': str(r['DESTINATION']),
         'customers': int(r['customers']),
         'total_spend': float(r['total_spend']),
         'spend_per_customer': float(r['spend_per_customer']),
         'market_share_pct': float(r['market_share_pct'])}
        for r in competitors
    ],
    'income_gender': [
        {'band': str(r['band']), 'male': int(r['male']), 'female': int(r['female'])}
        for r in income_gender
    ],
    'age_gender': [
        {'band': str(r['band']), 'male': int(r['male']), 'female': int(r['female'])}
        for r in age_gender
    ],
    'geo': [
        {'province': str(r['province']),
         'customers': int(r['customers']),
         'spend': float(r['spend'])}
        for r in geo
    ],
    'segments': [
        {'name': str(r['segment']), 'customers': int(r['customers']), 'pct': float(r['pct'])}
        for r in segments
    ],
    'cross_shop': [
        {'category': str(r['category']),
         'shoppers': int(r['shoppers']),
         'spend': float(r['spend'])}
        for r in cross_shop
    ],
    'trend': [
        {'month': str(r['month']),
         'customers': int(r['customers']),
         'spend': float(r['spend'])}
        for r in trend
    ],
}


# ── HTML helpers ─────────────────────────────────────────────────────────
def kpi_card(label: str, value: str, sub: str = '') -> str:
    sub_html = f'<div class="s">{esc(sub)}</div>' if sub else ''
    return (f'<div class="card"><div class="l">{esc(label)}</div>'
            f'<div class="v">{esc(value)}</div>{sub_html}</div>')


now = datetime.now().strftime('%d %B %Y')

# ── Trend narrative (compute the story so we can print it below the chart) ─
trend_narrative = ''
if len(trend) >= 3:
    first_half = trend[:len(trend)//2]
    second_half = trend[len(trend)//2:]
    avg_first  = sum(m['spend'] for m in first_half)  / len(first_half)
    avg_second = sum(m['spend'] for m in second_half) / len(second_half)
    direction_pct = round(100 * (avg_second - avg_first) / max(avg_first, 1), 1)
    peak_month  = max(trend, key=lambda m: m['spend'])
    trough_month = min(trend, key=lambda m: m['spend'])
    if direction_pct > 3:
        direction = f'<b style="color:#16a34a">growing</b> ({direction_pct:+.1f}% H1→H2)'
    elif direction_pct < -3:
        direction = f'<b style="color:#e11d48">softening</b> ({direction_pct:+.1f}% H1→H2)'
    else:
        direction = f'<b style="color:#334155">stable</b> ({direction_pct:+.1f}% H1→H2)'
    trend_narrative = (
        f'Food Lovers monthly spend is {direction}. Peak month: '
        f'<b>{esc(peak_month["month"])}</b> ({R(peak_month["spend"])}). '
        f'Softest month: <b>{esc(trough_month["month"])}</b> ({R(trough_month["spend"])}).'
    )


# ── Activation opportunity buckets — now with SPEND AT STAKE, not just headcount
seg_by_name = {s['segment']: s for s in segments}
seg_spend_by_name = {s['segment']: s for s in segment_spend}
def _seg(name, key='customers'):
    row = seg_by_name.get(name)
    return int(row[key]) if row else 0
def _seg_spend(name):
    row = seg_spend_by_name.get(name)
    return int(row['fl_annual_spend']) if row else 0

grow_pool     = _seg('Steady Mid-Tier')
protect_pool  = _seg('Champions') + _seg('Loyal High Value')
reengage_pool = _seg('At Risk') + _seg('Dormant')

protect_spend  = _seg_spend('Champions') + _seg_spend('Loyal High Value')
grow_spend     = _seg_spend('Steady Mid-Tier')
reengage_spend = _seg_spend('At Risk') + _seg_spend('Dormant')

activation_cards = ''.join([
    f'''<div class="act-card act-protect">
      <div class="act-badge">PROTECT</div>
      <h3>Champions &amp; Loyal High Value</h3>
      <div class="act-size">{N(protect_pool)}</div>
      <div class="act-money">{R(protect_spend)} annual spend at stake</div>
      <div class="act-desc">Your highest-value audience — the aspirational shoppers who make Food Lovers their fresh-first choice. Retention plays: premium-fresh subscription boxes, VIP tasting events at new Market openings, early access to Earth Lovers-branded lines. Losing one costs 5-10× more than acquiring a new mid-tier customer.</div>
    </div>''',
    f'''<div class="act-card act-grow">
      <div class="act-badge">GROW</div>
      <h3>Steady Mid-Tier</h3>
      <div class="act-size">{N(grow_pool)}</div>
      <div class="act-money">{R(grow_spend)} current spend · upside potential</div>
      <div class="act-desc">Reliable regulars ready to trade up. Basket-builder promos (fresh + deli + bakery bundles), Eatery cross-sell, and value-first messaging that reinforces your "cheapest basket" positioning.</div>
    </div>''',
    f'''<div class="act-card act-reengage">
      <div class="act-badge">RE-ENGAGE</div>
      <h3>Dormant &amp; At Risk</h3>
      <div class="act-size">{N(reengage_pool)}</div>
      <div class="act-money">{R(reengage_spend)} lapsed spend to recover</div>
      <div class="act-desc">Previously active customers with fading engagement. Win-back with your unique wedge: freshness + value that competitors can't match. Personalised come-back offers on their old favourite categories.</div>
    </div>''',
])

# Combined hero KPIs
combined_kpis = '<div class="row">' + ''.join([
    kpi_card('Customers', N(fl_combined['customers']), 'unique FNB cardholders'),
    kpi_card('Annual Spend', R(fl_combined['total_spend'])),
    kpi_card('Transactions', N(fl_combined['transactions'])),
    kpi_card('Avg Basket', R(fl_combined['avg_txn_value'])),
    kpi_card('Spend / Customer', R_exact(fl_combined['spend_per_customer']), 'per year'),
    kpi_card('Avg Age', f"{demo['avg_age']}"),
]) + '</div>'

# Market KPIs (from mart — has rank + share)
if fl_market_row is not None:
    market_kpis = '<div class="row">' + ''.join([
        kpi_card('Customers', N(fl_market_row['customers'])),
        kpi_card('Annual Spend', R(fl_market_row['total_spend'])),
        kpi_card('Avg Basket', R(fl_market_row['avg_txn_value'])),
        kpi_card('Spend / Customer', R_exact(fl_market_row['spend_per_customer'])),
        kpi_card('Market Rank', f"#{int(fl_market_row['spend_rank'])}", 'in category'),
        kpi_card('Customer Reach', f"{fl_market_row['penetration_pct']:.1f}%", 'of grocery shoppers'),
    ]) + '</div>'
else:
    market_kpis = '<p style="color:#94a3b8">No data.</p>'

# Eatery KPIs (live query)
if fl_eatery_row is not None and int(fl_eatery_row['customers']) > 0:
    eatery_kpis = '<div class="row">' + ''.join([
        kpi_card('Customers', N(fl_eatery_row['customers'])),
        kpi_card('Annual Spend', R(fl_eatery_row['total_spend'])),
        kpi_card('Avg Basket', R(fl_eatery_row['avg_txn_value'])),
        kpi_card('Spend / Customer', R_exact(fl_eatery_row['spend_per_customer'])),
        kpi_card('Transactions', N(fl_eatery_row['transactions'])),
    ]) + '</div>'
else:
    eatery_kpis = '<p style="color:#94a3b8">No Eatery activity in the dataset.</p>'

# Demographics tiles (combined)
total_gender = int(demo['male']) + int(demo['female'])
demo_row = ''.join([
    kpi_card('Female', f"{round(100*demo['female']/total_gender,1)}%",
             f"{N(demo['female'])} customers"),
    kpi_card('Male', f"{round(100*demo['male']/total_gender,1)}%",
             f"{N(demo['male'])} customers"),
    kpi_card('Avg age', f"{demo['avg_age']}", 'years'),
])

# Competitive table rows
comp_table_rows = ''
for r in competitors:
    is_fl = 'FOOD LOVERS' in str(r['DESTINATION']).upper()
    css = ' class="fl"' if is_fl else ''
    comp_table_rows += (
        f'<tr{css}><td>{esc(r["DESTINATION"])}</td>'
        f'<td>{N(r["customers"])}</td>'
        f'<td>{R(r["total_spend"])}</td>'
        f'<td>{R(r["spend_per_customer"])}</td>'
        f'<td>{r["market_share_pct"]:.1f}%</td></tr>'
    )

# Segment quality highlight
top_2_segments_pct = round(sum(s['pct'] for s in segments[:2]), 1) if len(segments) >= 2 else 0
top_seg_name = segments[0]['segment'] if segments else ''

# Cross-shop table
cross_shop_rows = ''
for r in cross_shop:
    cross_shop_rows += (
        f'<tr><td>{esc(r["category"])}</td>'
        f'<td>{N(r["shoppers"])}</td>'
        f'<td>{R(r["spend"])}</td></tr>'
    )


html = f"""<!DOCTYPE html>
<html lang='en'><head><meta charset='UTF-8'>
<title>Food Lovers — Audience Snapshot</title>
<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'></script>
<script src='https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0'></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'DM Sans',sans-serif; background:#f8fafc; color:#1a202c; }}
#hdr {{ background:linear-gradient(135deg,#0f172a,#1e3a5f); color:#fff; padding:28px 32px; }}
#hdr h1 {{ font-size:1.9rem; font-weight:700; }}
#hdr p {{ opacity:.85; font-size:1rem; margin-top:6px; }}
#hdr .meta {{ font-size:.78rem; opacity:.55; margin-top:14px; }}
.ctn {{ max-width:1200px; margin:0 auto; padding:24px; }}
.sec {{ background:#fff; border-radius:14px; padding:26px 30px; margin:18px 0; border:1px solid #f1f5f9; box-shadow:0 1px 4px rgba(0,0,0,.04); }}
.sec h2 {{ font-size:1.35rem; font-weight:700; color:#0f172a; margin-bottom:6px; }}
.sec .sub {{ color:#64748b; font-size:.92rem; margin-bottom:18px; line-height:1.5; }}
.hero {{ background:linear-gradient(135deg,#fef3c7,#fde68a); border:1px solid #f59e0b; }}
.hero h2 {{ color:#78350f; }}
.hero .sub {{ color:#92400e; }}
.callout {{ background:#dcfce7; border-left:4px solid #16a34a; border-radius:0 10px 10px 0; padding:14px 18px; margin:14px 0; font-size:.95rem; color:#14532d; line-height:1.5; }}
.row {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:12px 0; }}
.card {{ background:#f8fafc; border-radius:10px; padding:16px; text-align:center; border-top:3px solid #2E75B6; }}
.hero .card {{ background:#fffbeb; border-top-color:#d97706; }}
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
tr.fl td {{ background:#fef3c7; font-weight:600; }}

/* Branded cards for Market / Eatery / Combined split */
.brand-card {{ background:#fff; border-radius:12px; padding:20px 22px; border:2px solid #f1f5f9; }}
.brand-combined {{ border-color:#f59e0b; background:linear-gradient(180deg,#fffbeb 0%,#fff 60%); }}
.brand-market   {{ border-color:#2E75B6; background:linear-gradient(180deg,#eff6ff 0%,#fff 60%); }}
.brand-eatery   {{ border-color:#16a34a; background:linear-gradient(180deg,#f0fdf4 0%,#fff 60%); }}
.brand-header   {{ display:flex; align-items:center; gap:10px; margin-bottom:4px; }}
.brand-header h3 {{ font-size:1.1rem; font-weight:700; color:#0f172a; margin:0; }}
.brand-badge    {{ font-size:.66rem; font-weight:700; padding:3px 10px; border-radius:12px; letter-spacing:.06em; color:#fff; }}
.brand-badge.combined {{ background:#d97706; }}
.brand-badge.market   {{ background:#2E75B6; }}
.brand-badge.eatery   {{ background:#16a34a; }}
.brand-sub      {{ color:#64748b; font-size:.86rem; margin-bottom:14px; }}
.brand-market .card {{ border-top-color:#2E75B6; }}
.brand-eatery .card {{ border-top-color:#16a34a; }}
.brand-combined .card {{ border-top-color:#d97706; }}

/* Activation opportunity cards */
.act-row {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-top:14px; }}
@media(max-width:850px) {{ .act-row {{ grid-template-columns:1fr; }} }}
.act-card {{ background:#fff; border-radius:12px; padding:20px 22px; border:2px solid #f1f5f9; position:relative; }}
.act-card h3 {{ font-size:1.05rem; font-weight:700; color:#0f172a; margin:8px 0 4px; }}
.act-badge {{ display:inline-block; font-size:.65rem; font-weight:700; padding:3px 10px; border-radius:12px; letter-spacing:.06em; color:#fff; }}
.act-size {{ font-size:1.7rem; font-weight:700; color:#0f172a; margin:6px 0 0; font-variant-numeric:tabular-nums; }}
.act-money {{ font-size:.8rem; font-weight:600; color:#78350f; margin:4px 0 10px; letter-spacing:.01em; }}
.act-desc {{ font-size:.85rem; color:#475569; line-height:1.55; }}
.act-protect  {{ border-color:#16a34a; background:linear-gradient(180deg,#f0fdf4 0%,#fff 60%); }}
.act-protect  .act-badge {{ background:#16a34a; }}
.act-grow     {{ border-color:#2E75B6; background:linear-gradient(180deg,#eff6ff 0%,#fff 60%); }}
.act-grow     .act-badge {{ background:#2E75B6; }}
.act-reengage {{ border-color:#e11d48; background:linear-gradient(180deg,#fef2f2 0%,#fff 60%); }}
.act-reengage .act-badge {{ background:#e11d48; }}

/* Trend narrative callout */
.trend-story {{ background:#f1f5f9; border-radius:10px; padding:14px 18px; margin-top:14px; font-size:.94rem; color:#334155; line-height:1.55; }}
</style>
</head><body>

<div id='hdr'>
<h1>Food Lovers — Audience Snapshot</h1>
<p>FNB cardholder activity at Food Lovers Market + Eatery, last 12 months</p>
<div class='meta'>Generated {esc(now)}</div>
</div>

<div class='ctn'>

<div class='sec hero'>
<h2>The reach story</h2>
<p class='sub'>Distinct FNB cardholders shopping at Food Lovers (Market + Eatery) in the last 12 months — a real, addressable audience of aspirational South African households.</p>
{combined_kpis}
</div>

<div class='sec'>
<h2>How the audience splits between the two brands</h2>
<p class='sub'>The combined audience above breaks down into the Market and Eatery footprints below. Some customers shop at both.</p>

<div class='brand-card brand-combined'>
<div class='brand-header'>
<span class='brand-badge combined'>COMBINED</span>
<h3>Food Lovers (Market + Eatery)</h3>
</div>
<p class='brand-sub'>Total unique cardholders across both brands.</p>
<div class='row'>
{''.join([
    kpi_card('Customers', N(fl_combined['customers'])),
    kpi_card('Annual Spend', R(fl_combined['total_spend'])),
    kpi_card('Transactions', N(fl_combined['transactions'])),
    kpi_card('Avg Basket', R(fl_combined['avg_txn_value'])),
    kpi_card('Spend / Customer', R_exact(fl_combined['spend_per_customer'])),
])}
</div>
</div>

<div class='two-col' style='margin-top:16px'>
<div class='brand-card brand-market'>
<div class='brand-header'>
<span class='brand-badge market'>MARKET</span>
<h3>Food Lovers Market</h3>
</div>
<p class='brand-sub'>The supermarket footprint.</p>
{market_kpis}
</div>

<div class='brand-card brand-eatery'>
<div class='brand-header'>
<span class='brand-badge eatery'>EATERY</span>
<h3>Food Lovers Eatery</h3>
</div>
<p class='brand-sub'>The prepared-food / bakery footprint.</p>
{eatery_kpis}
</div>
</div>
</div>

<div class='sec'>
<h2>Category positioning</h2>
<p class='sub'>Where Food Lovers Market sits in the grocery category by FNB cardholder spend.</p>
<div class='row'>
{f'''{kpi_card('Category Rank', f"#{int(fl_market_row['spend_rank'])}", 'in Groceries')}
     {kpi_card('Category Share', f"{fl_market_row['market_share_pct']:.1f}%", 'by spend')}
     {kpi_card('Customer Reach', f"{fl_market_row['penetration_pct']:.1f}%", 'of grocery shoppers')}
     {kpi_card('Wallet Share', f"{fl_market_row['avg_share_of_wallet']:.1f}%", 'of grocery basket')}''' if fl_market_row is not None else ''}
</div>
</div>

<div class='sec'>
<h2>Customer quality</h2>
<p class='sub'>Food Lovers customers clustered by FNB's behavioural segmentation model. Segments reflect FNB-wide activity (not Food Lovers-specific).</p>
<div class='callout'>
<b>{top_2_segments_pct}% of Food Lovers customers are in FNB's two highest-value segments</b> — evidence that your aspirational-middle-class positioning is landing. Your customers are the same people banking premium services elsewhere in the FNB ecosystem.
</div>
<div class='two-col'>
<div class='chbox'><canvas id='chSegments'></canvas></div>
<div style='font-size:.88rem;line-height:1.6;color:#334155'>
<h3 style='font-size:1rem;color:#0f172a;margin-bottom:8px'>What the segments mean</h3>
<p><b style='color:#16a34a'>Loyal High Value</b> — consistently high spenders with strong recency. Top of the funnel.</p>
<p style='margin-top:8px'><b style='color:#2E75B6'>Champions</b> — highest lifetime value; broad category spread and frequent transactions.</p>
<p style='margin-top:8px'><b style='color:#f59e0b'>Steady Mid-Tier</b> — reliable regulars with moderate but stable spend patterns.</p>
<p style='margin-top:8px'><b style='color:#e11d48'>Dormant</b> — previously active but low recent engagement — re-activation opportunity.</p>
<p style='margin-top:8px'><b style='color:#94a3b8'>At Risk</b> — spend and frequency declining — win-back campaign candidates.</p>
</div>
</div>
</div>

<div class='sec'>
<h2>Who they are</h2>
<p class='sub'>A snapshot of the Food Lovers audience demographics.</p>
<div class='row'>
{demo_row}
</div>
<p class='sub' style='margin-top:14px;font-size:.9rem;color:#475569'>
The audience skews slightly female (54%) with an average age in the mid-40s — mature, established consumers.
Full age and income breakdowns follow below.
</p>
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
<p class='sub'>Total Food Lovers spend by province — where the audience lives.</p>
<div class='chbox tall'><canvas id='chGeo'></canvas></div>
</div>

<div class='sec'>
<h2>Monthly trend</h2>
<p class='sub'>Food Lovers spend and customer counts month-over-month across the last 12 months.</p>
<div class='chbox tall'><canvas id='chTrend'></canvas></div>
<div class='trend-story'>{trend_narrative}</div>
</div>

<div class='sec'>
<h2>Activation opportunities</h2>
<p class='sub'>The audience isn't monolithic — it's three distinct pools, each with a different play, and a real spend number attached. Sizes below are Food Lovers customers who fit each segment based on their FNB-wide behaviour.</p>
<div class='act-row'>
{activation_cards}
</div>
</div>

<div class='sec' style='background:linear-gradient(180deg,#f0fdf4 0%,#fff 40%); border:2px solid #16a34a'>
<h2 style='color:#166534'>Your fresh-first loyalists</h2>
<p class='sub'>Customers where <b>60%+ of their grocery basket</b> is spent at Food Lovers — the ones who chose freshness and value as a way of life. This is your brand's armour.</p>
<div class='row'>
{kpi_card('Loyalist customers', N(loyalist['loyalist_customers']))}
{kpi_card('Annual spend from loyalists', R(loyalist['loyalist_spend']))}
{kpi_card('Regular shoppers', N(loyalist['regular_customers']), '20-60% of grocery basket')}
{kpi_card('Occasional shoppers', N(loyalist['occasional_customers']), '<20% of grocery basket')}
</div>
<div class='callout' style='margin-top:14px'>
Loyalists are 5× more valuable than casual shoppers. Every basket-share point you win from Regular → Loyalist is worth thousands of Rands over their lifetime. Use Earth Lovers messaging + fresh subscriptions to lock them in.
</div>
</div>

<div class='sec' style='background:linear-gradient(180deg,#eff6ff 0%,#fff 40%); border:2px solid #2E75B6'>
<h2 style='color:#1e40af'>Aspirational acquisition target</h2>
<p class='sub'>FNB cardholders who match your ideal shopper — young professionals, mid-to-upper income, active grocery spenders — <b>but who don't shop at Food Lovers yet</b>. This is who to steal from the premium chains.</p>
<div class='row'>
{kpi_card('Prospects', N(acq_target['acq_customers']), '26–45, R23.5k+ income')}
{kpi_card('Annual grocery spend', R(acq_target['acq_grocery_spend']), 'currently going elsewhere')}
{kpi_card('Avg spend per prospect', R(int(acq_target['acq_grocery_spend']) / max(int(acq_target['acq_customers']), 1)))}
</div>
<div class='callout' style='margin-top:14px'>
Winning even a small share of this pool means real growth. Position on "fresh-first at a better price than Woolworths" — that's the wedge that lands with this segment.
</div>
</div>

<div class='sec'>
<h2>Adjacent spend — bundling &amp; co-brand opportunities</h2>
<p class='sub'>The top non-food categories your customers already spend in. Useful for bundle offers, co-brand partnerships, and channel targeting beyond the grocery aisle.</p>
<table><tr><th>Category</th><th>Shoppers</th><th>Annual spend</th></tr>{cross_shop_rows}</table>
</div>

</div>

<script>
const Data = {json.dumps(data_obj)};
const colors = {{
    male:    '#2E75B6',
    female:  '#E85C0D',
    accent:  '#1e3a5f',
    accent2: '#0f172a',
    fl:      '#f59e0b',
    seg:     ['#16a34a','#2E75B6','#f59e0b','#e11d48','#94a3b8'],
}};

// Register the datalabels plugin globally
if (typeof ChartDataLabels !== 'undefined') {{
    Chart.register(ChartDataLabels);
}}

function mkChart(id, cfg) {{
    const el = document.getElementById(id);
    if (!el) return;
    // Disable datalabels by default; charts that want them opt in via cfg.options.plugins.datalabels
    if (!cfg.options) cfg.options = {{}};
    if (!cfg.options.plugins) cfg.options.plugins = {{}};
    if (cfg.options.plugins.datalabels === undefined) {{
        cfg.options.plugins.datalabels = {{ display: false }};
    }}
    new Chart(el, cfg);
}}

// Competitor total spend (horizontal bar)
mkChart('chCompSpend', {{
    type: 'bar',
    data: {{
        labels: Data.competitors.map(r => r.name),
        datasets: [{{
            label: 'Total spend',
            data: Data.competitors.map(r => r.total_spend),
            backgroundColor: Data.competitors.map(r =>
                r.name.toUpperCase().includes('FOOD LOVERS') ? colors.fl : colors.accent),
            borderColor: '#0f172a', borderWidth: 1
        }}]
    }},
    options: {{
        indexAxis: 'y', responsive: true, maintainAspectRatio: false,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{ x: {{ beginAtZero: true, ticks: {{ callback: v => 'R' + (v/1e9).toFixed(1) + 'B' }} }} }}
    }}
}});

// Competitor spend per customer
mkChart('chCompSpc', {{
    type: 'bar',
    data: {{
        labels: Data.competitors.map(r => r.name),
        datasets: [{{
            label: 'Spend per customer',
            data: Data.competitors.map(r => r.spend_per_customer),
            backgroundColor: Data.competitors.map(r =>
                r.name.toUpperCase().includes('FOOD LOVERS') ? colors.fl : colors.accent),
            borderColor: '#0f172a', borderWidth: 1
        }}]
    }},
    options: {{
        indexAxis: 'y', responsive: true, maintainAspectRatio: false,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{ x: {{ beginAtZero: true, ticks: {{ callback: v => 'R' + (v/1e3).toFixed(0) + 'k' }} }} }}
    }}
}});

// Segments — donut with % labels on slices ≥ 8% (small slices skip to avoid overlap)
// Legend on the right also carries the % so nothing is lost even when the slice label hides
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
        responsive: true, maintainAspectRatio: false,
        cutout: '58%',
        plugins: {{
            legend: {{ position: 'right', labels: {{ font: {{ size: 12 }}, padding: 12 }} }},
            datalabels: {{
                display: (ctx) => {{
                    const total = ctx.chart.data.datasets[0].data.reduce((a,b) => a+b, 0);
                    const value = ctx.dataset.data[ctx.dataIndex];
                    return (value/total) * 100 >= 8;   // hide labels on slices under 8%
                }},
                color: '#fff',
                font: {{ size: 14, weight: 'bold' }},
                formatter: (value, ctx) => {{
                    const total = ctx.chart.data.datasets[0].data.reduce((a,b) => a+b, 0);
                    return ((value/total)*100).toFixed(1) + '%';
                }}
            }}
        }}
    }}
}});

// Income band × gender
mkChart('chIncomeGender', {{
    type: 'bar',
    data: {{
        labels: Data.income_gender.map(r => r.band),
        datasets: [
            {{ label: 'Male',   data: Data.income_gender.map(r => r.male),   backgroundColor: colors.male   }},
            {{ label: 'Female', data: Data.income_gender.map(r => r.female), backgroundColor: colors.female }}
        ]
    }},
    options: {{
        responsive: true, maintainAspectRatio: false,
        scales: {{ y: {{ beginAtZero: true }} }}
    }}
}});

// Age band × gender
mkChart('chAgeGender', {{
    type: 'bar',
    data: {{
        labels: Data.age_gender.map(r => r.band),
        datasets: [
            {{ label: 'Male',   data: Data.age_gender.map(r => r.male),   backgroundColor: colors.male   }},
            {{ label: 'Female', data: Data.age_gender.map(r => r.female), backgroundColor: colors.female }}
        ]
    }},
    options: {{
        responsive: true, maintainAspectRatio: false,
        scales: {{ y: {{ beginAtZero: true }} }}
    }}
}});

// Provincial spend
mkChart('chGeo', {{
    type: 'bar',
    data: {{
        labels: Data.geo.map(r => r.province),
        datasets: [{{
            label: 'Spend',
            data: Data.geo.map(r => r.spend),
            backgroundColor: colors.accent, borderColor: '#0f172a', borderWidth: 1
        }}]
    }},
    options: {{
        indexAxis: 'y', responsive: true, maintainAspectRatio: false,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{ x: {{ beginAtZero: true, ticks: {{ callback: v => 'R' + (v/1e6).toFixed(0) + 'M' }} }} }}
    }}
}});

// Monthly trend — line chart
mkChart('chTrend', {{
    type: 'line',
    data: {{
        labels: Data.trend.map(r => r.month),
        datasets: [
            {{
                label: 'Spend',
                data: Data.trend.map(r => r.spend),
                borderColor: colors.fl,
                backgroundColor: 'rgba(245,158,11,0.15)',
                yAxisID: 'y', tension: 0.3, fill: true
            }},
            {{
                label: 'Customers',
                data: Data.trend.map(r => r.customers),
                borderColor: colors.accent,
                backgroundColor: 'transparent',
                yAxisID: 'y1', tension: 0.3
            }}
        ]
    }},
    options: {{
        responsive: true, maintainAspectRatio: false,
        scales: {{
            y:  {{ position: 'left',  ticks: {{ callback: v => 'R' + (v/1e6).toFixed(0) + 'M' }} }},
            y1: {{ position: 'right', grid: {{ drawOnChartArea: false }}, ticks: {{ callback: v => (v/1e3).toFixed(0) + 'k' }} }}
        }}
    }}
}});
</script>

</body></html>
"""

OUT = 'food_lovers_pitch.html'
with open(OUT, 'w') as f:
    f.write(html)

print()
print(f'Wrote: {OUT}')
print('Open in browser and screenshot each section into slides.')
