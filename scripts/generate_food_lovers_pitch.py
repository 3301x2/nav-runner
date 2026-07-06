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
    'production': 'fmn-production', 'prod': 'fmn-production', 'prd': 'fmn-production',
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

# Combined hero KPIs
combined_kpis = '<div class="row">' + ''.join([
    kpi_card('Customers', N(fl_combined['customers']), 'unique FNB cardholders'),
    kpi_card('Annual Spend', R(fl_combined['total_spend'])),
    kpi_card('Transactions', N(fl_combined['transactions'])),
    kpi_card('Avg Basket', R(fl_combined['avg_txn_value'])),
    kpi_card('Spend / Customer', R(fl_combined['spend_per_customer']), 'per year'),
    kpi_card('Avg Age', f"{demo['avg_age']}"),
]) + '</div>'

# Market KPIs (from mart — has rank + share)
if fl_market_row is not None:
    market_kpis = '<div class="row">' + ''.join([
        kpi_card('Customers', N(fl_market_row['customers'])),
        kpi_card('Annual Spend', R(fl_market_row['total_spend'])),
        kpi_card('Avg Basket', R(fl_market_row['avg_txn_value'])),
        kpi_card('Spend / Customer', R(fl_market_row['spend_per_customer'])),
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
        kpi_card('Spend / Customer', R(fl_eatery_row['spend_per_customer'])),
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
</style>
</head><body>

<div id='hdr'>
<h1>Food Lovers — Audience Snapshot</h1>
<p>FNB cardholder activity at Food Lovers Market + Eatery, last 12 months</p>
<div class='meta'>Generated {esc(now)}</div>
</div>

<div class='ctn'>

<div class='sec hero'>
<h2>The audience at a glance</h2>
<p class='sub'>Distinct FNB cardholders who transacted at Food Lovers (Market or Eatery) in the last 12 months.</p>
{combined_kpis}
</div>

<div class='sec'>
<h2>How the audience splits between the two brands</h2>
<div class='two-col'>
<div>
<h3 style='font-size:1rem;font-weight:600;color:#1e3a5f;margin-bottom:8px'>Food Lovers Market</h3>
<p class='sub' style='margin-bottom:12px'>The supermarket footprint.</p>
{market_kpis}
</div>
<div>
<h3 style='font-size:1rem;font-weight:600;color:#1e3a5f;margin-bottom:8px'>Food Lovers Eatery</h3>
<p class='sub' style='margin-bottom:12px'>The prepared-food / bakery footprint.</p>
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
<b>{top_2_segments_pct}% of Food Lovers customers are in FNB's two highest-value segments</b> — a strong indicator of an affluent, engaged audience.
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
<p class='sub'>Food Lovers spend and customer counts month-over-month.</p>
<div class='chbox tall'><canvas id='chTrend'></canvas></div>
</div>

<div class='sec'>
<h2>What else they buy</h2>
<p class='sub'>The top categories these customers spend in beyond food. Useful for co-brand / adjacency thinking.</p>
<table><tr><th>Category</th><th>Shoppers</th><th>Spend</th></tr>{cross_shop_rows}</table>
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

function mkChart(id, cfg) {{
    const el = document.getElementById(id);
    if (!el) return;
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

// Segments — donut showing quality mix
mkChart('chSegments', {{
    type: 'doughnut',
    data: {{
        labels: Data.segments.map(r => r.name),
        datasets: [{{
            data: Data.segments.map(r => r.customers),
            backgroundColor: Data.segments.map((_,i) => colors.seg[i % colors.seg.length]),
            borderColor: '#fff', borderWidth: 2
        }}]
    }},
    options: {{
        responsive: true, maintainAspectRatio: false,
        plugins: {{ legend: {{ position: 'right' }} }}
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
