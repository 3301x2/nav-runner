#!/usr/bin/env python3
"""
Food Lovers pitch — screenshot-ready HTML with clean numbers + Chart.js
charts. Produces TWO grids (Market only + Market+Eatery combined) so the
audience can decide.

Every KPI is scope-labelled explicitly:
    • FNB-wide
    • Groceries category
    • Food Lovers (Market only)
    • Food Lovers (Market + Eatery combined)

Segment/CLV/churn intentionally EXCLUDED from this deck. Those models are
FNB-wide (not client-specific) and if included must carry a caveat that
Simphiwe didn't add. Cleaner to leave them out for now.

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

# Groceries category totals (for context/share math)
groc = q(f"""
    SELECT
        COUNT(DISTINCT UNIQUE_ID) AS customers,
        SUM(dest_txn_count)       AS transactions,
        ROUND(SUM(dest_spend), 0) AS spend
    FROM `{PROJECT}.analytics.int_customer_category_spend`
    WHERE CATEGORY_TWO = 'Groceries'
""").iloc[0]

# Food Lovers Market only
fl_market = q(f"""
    SELECT
        customers,
        transactions,
        total_spend,
        avg_txn_value,
        spend_per_customer,
        market_share_pct,
        penetration_pct,
        avg_share_of_wallet,
        spend_rank
    FROM `{PROJECT}.marts.mart_destination_benchmarks`
    WHERE CATEGORY_TWO = 'Groceries'
      AND UPPER(DESTINATION) = 'FOOD LOVERS MARKET'
""")
if fl_market.empty:
    fl_market_row = None
else:
    fl_market_row = fl_market.iloc[0]

# Food Lovers Eatery only
fl_eatery = q(f"""
    SELECT
        customers,
        transactions,
        total_spend,
        avg_txn_value,
        spend_per_customer,
        market_share_pct,
        penetration_pct,
        avg_share_of_wallet,
        spend_rank
    FROM `{PROJECT}.marts.mart_destination_benchmarks`
    WHERE CATEGORY_TWO = 'Groceries'
      AND UPPER(DESTINATION) = 'FOOD LOVERS EATERY'
""")
fl_eatery_row = fl_eatery.iloc[0] if not fl_eatery.empty else None

# Combined (union of customer bases across BOTH DESTINATIONs regardless of category)
# NOTE: We intentionally DO NOT filter on CATEGORY_TWO here.
# Food Lovers Market lives in 'Groceries', but Food Lovers Eatery lives in
# a different category (Fast Food / Restaurants). Filtering on 'Groceries'
# would silently drop the Eatery and produce a wrong "combined" total.
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

# Validation: recompute the combined customer base from scratch using set logic
# and cross-check. If the two disagree by more than 1%, halt the script.
# This prevents silent-scope bugs from ever reaching a client deck.
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

print(f'  Combined customer base validation:')
print(f'    Market:              {int(fl_validate["market_customers"]):>10,}')
print(f'    Eatery:              {int(fl_validate["eatery_customers"]):>10,}')
print(f'    In both:             {int(fl_validate["in_both"]):>10,}')
print(f'    True union (M+E−∩):  {validation_union:>10,}')
print(f'    Primary query said:  {primary_combined:>10,}')
print(f'    Delta:               {delta_pct:.3f}%')

if delta_pct > 1.0:
    sys.exit(
        f'\n❌ ABORTING: combined customer base disagrees by {delta_pct:.2f}%.\n'
        f'   Primary query:    {primary_combined:,}\n'
        f'   Set-logic union:  {validation_union:,}\n'
        f'   Refusing to generate a pitch with unreliable numbers.'
    )
print(f'  ✓ Validation passed (delta {delta_pct:.3f}% ≤ 1%)')

# Competitive set (top 8 in Groceries)
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
    LIMIT 10
""").to_dict('records')

# Demographics for combined audience — age × gender + income band × gender
demo = q(f"""
    WITH fl_custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE UPPER(DESTINATION) IN ('FOOD LOVERS MARKET', 'FOOD LOVERS EATERY')
    )
    SELECT
        COUNT(*)                                                                                  AS customers,
        ROUND(AVG(c.age), 1)                                                                      AS avg_age,
        COUNT(DISTINCT CASE WHEN c.gender_label = 'Male'    THEN c.UNIQUE_ID END)                 AS male,
        COUNT(DISTINCT CASE WHEN c.gender_label = 'Female'  THEN c.UNIQUE_ID END)                 AS female,
        COUNT(DISTINCT CASE WHEN c.age BETWEEN 18 AND 25 THEN c.UNIQUE_ID END)                    AS age_18_25,
        COUNT(DISTINCT CASE WHEN c.age BETWEEN 26 AND 35 THEN c.UNIQUE_ID END)                    AS age_26_35,
        COUNT(DISTINCT CASE WHEN c.age BETWEEN 36 AND 45 THEN c.UNIQUE_ID END)                    AS age_36_45,
        COUNT(DISTINCT CASE WHEN c.age BETWEEN 46 AND 60 THEN c.UNIQUE_ID END)                    AS age_46_60,
        COUNT(DISTINCT CASE WHEN c.age > 60 THEN c.UNIQUE_ID END)                                 AS age_60_plus
    FROM fl_custs f
    JOIN `{PROJECT}.staging.stg_customers` c USING (UNIQUE_ID)
""").iloc[0]

# Income band by gender (matches Simphiwe's left chart on slide 2)
income_gender = q(f"""
    WITH fl_custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE UPPER(DESTINATION) IN ('FOOD LOVERS MARKET', 'FOOD LOVERS EATERY')
    )
    SELECT
        c.income_group,
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
        c.age_group,
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

# Spend by province (top 8)
geo = q(f"""
    WITH fl_custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM `{PROJECT}.analytics.int_customer_category_spend`
        WHERE UPPER(DESTINATION) IN ('FOOD LOVERS MARKET', 'FOOD LOVERS EATERY')
    )
    SELECT
        t.PROVINCE,
        COUNT(DISTINCT t.UNIQUE_ID) AS customers,
        ROUND(SUM(t.trns_amt), 0)   AS spend
    FROM fl_custs f
    JOIN `{PROJECT}.staging.stg_transactions` t USING (UNIQUE_ID)
    WHERE UPPER(t.DESTINATION) IN ('FOOD LOVERS MARKET', 'FOOD LOVERS EATERY')
      AND t.PROVINCE IS NOT NULL
    GROUP BY t.PROVINCE
    ORDER BY spend DESC
    LIMIT 8
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
        {'band': str(r['income_group']), 'male': int(r['male']), 'female': int(r['female'])}
        for r in income_gender
    ],
    'age_gender': [
        {'band': str(r['age_group']), 'male': int(r['male']), 'female': int(r['female'])}
        for r in age_gender
    ],
    'geo': [
        {'province': str(r['PROVINCE']),
         'customers': int(r['customers']),
         'spend': float(r['spend'])}
        for r in geo
    ],
}


# ── Build HTML ───────────────────────────────────────────────────────────
def kpi_card(label: str, value: str, sub: str = '') -> str:
    sub_html = f'<div class="s">{esc(sub)}</div>' if sub else ''
    return (f'<div class="card"><div class="l">{esc(label)}</div>'
            f'<div class="v">{esc(value)}</div>{sub_html}</div>')


def grid_kpis(row, scope_label: str) -> str:
    """Build a 6-tile KPI grid for a Food Lovers destination row."""
    if row is None or (hasattr(row, 'empty') and row.empty):
        return f'<p style="color:#94a3b8">No data for {esc(scope_label)}.</p>'
    return '<div class="row">' + ''.join([
        kpi_card('Customers', N(row.get('customers'))),
        kpi_card('Total Spend', R(row.get('total_spend'))),
        kpi_card('Transactions', N(row.get('transactions'))),
        kpi_card('Avg Transaction', R(row.get('avg_txn_value'))),
        kpi_card('Spend / Customer', R(row.get('spend_per_customer'))),
        kpi_card('Market Share', f"{row.get('market_share_pct', 0):.1f}%" if 'market_share_pct' in row else '—'),
    ]) + '</div>'


def grid_kpis_combined() -> str:
    """Combined view — computed live, has fewer fields."""
    fl_pct = round(100 * fl_combined['total_spend'] / groc['spend'], 2) if groc['spend'] else 0
    return '<div class="row">' + ''.join([
        kpi_card('Customers', N(fl_combined['customers'])),
        kpi_card('Total Spend', R(fl_combined['total_spend'])),
        kpi_card('Transactions', N(fl_combined['transactions'])),
        kpi_card('Avg Transaction', R(fl_combined['avg_txn_value'])),
        kpi_card('Spend / Customer', R(fl_combined['spend_per_customer'])),
        kpi_card('Share of Groceries', f'{fl_pct:.1f}%', 'by spend'),
    ]) + '</div>'


now = datetime.now().strftime('%d %B %Y')

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

demo_row = ''.join([
    kpi_card('Avg age', f"{demo['avg_age']}"),
    kpi_card('Male / Female',
             f"{round(100*demo['male']/(demo['male']+demo['female']),1)}% / "
             f"{round(100*demo['female']/(demo['male']+demo['female']),1)}%"),
    kpi_card('18-25', N(demo['age_18_25'])),
    kpi_card('26-35', N(demo['age_26_35'])),
    kpi_card('36-45', N(demo['age_36_45'])),
    kpi_card('46-60', N(demo['age_46_60'])),
    kpi_card('60+', N(demo['age_60_plus'])),
])

html = f"""<!DOCTYPE html>
<html lang='en'><head><meta charset='UTF-8'>
<title>Food Lovers — Audience Pitch</title>
<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'DM Sans',sans-serif;background:#f8fafc;color:#1a202c}}
#hdr{{background:linear-gradient(135deg,#0f172a,#1e3a5f);color:#fff;padding:24px 32px}}
#hdr h1{{font-size:1.6rem;font-weight:700}}
#hdr p{{opacity:.9;font-size:.9rem;margin-top:4px}}
#hdr .meta{{font-size:.75rem;opacity:.65;margin-top:10px}}
.ctn{{max-width:1200px;margin:0 auto;padding:20px 24px}}
.scope-note{{background:#fef9c3;border-left:4px solid #ca8a04;border-radius:0 8px 8px 0;padding:12px 16px;margin:16px 0;font-size:.85rem;color:#713f12}}
.callout{{border-radius:10px;padding:12px 16px;margin:12px 0;font-size:.9rem}}
.callout.good{{background:#dcfce7;border-left:4px solid #16a34a;color:#14532d}}
.sec{{background:#fff;border-radius:12px;padding:24px 26px;margin:16px 0;border:1px solid #f1f5f9;box-shadow:0 1px 3px rgba(0,0,0,.04)}}
.sec h2{{font-size:1.2rem;font-weight:700;color:#0f172a;margin-bottom:4px}}
.sec .sub{{color:#64748b;font-size:.85rem;margin-bottom:16px}}
.row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:10px 0}}
.card{{background:#f8fafc;border-radius:8px;padding:14px;text-align:center;border-top:3px solid #2E75B6}}
.card .l{{font-size:.7rem;color:#64748b;font-weight:500;text-transform:uppercase}}
.card .v{{font-size:1.3rem;font-weight:700;color:#0f172a;margin-top:4px}}
.card .s{{font-size:.7rem;color:#94a3b8;margin-top:2px}}
.chbox{{position:relative;height:280px;margin:12px 0}}
.chbox.tall{{height:340px}}
table{{width:100%;border-collapse:collapse;margin:10px 0;font-size:.83rem}}
th{{background:#0f172a;color:#fff;padding:9px 12px;text-align:left;font-size:.72rem;text-transform:uppercase}}
td{{padding:8px 12px;border-bottom:1px solid #f1f5f9}}
tr.fl td{{background:#fef3c7;font-weight:600}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
@media(max-width:800px){{.two-col{{grid-template-columns:1fr}}}}
</style>
</head><body>

<div id='hdr'>
<h1>Food Lovers — Audience Pitch</h1>
<p>Screenshot-ready view of Food Lovers' customer base in FNB card data</p>
<div class='meta'>Source: {esc(PROJECT)}.marts.mart_destination_benchmarks · Generated {now} · Window: rolling 12 months</div>
</div>

<div class='ctn'>

<div class='scope-note'>
<b>Every number below is explicitly scoped.</b> Category-total numbers (all Groceries, all FNB) live in their own callouts so they can't be mistaken for Food Lovers-specific stats. Segments / churn / CLV are intentionally excluded — they were built on FNB-wide behaviour, not Food Lovers behaviour, and need a caveat before being shown.
</div>

<div class='sec'>
<h2>Context: The Groceries category</h2>
<p class='sub'>Total FNB-cardholder spend in Groceries (all merchants) in the last 12 months. Use for context, NOT for Food Lovers-specific claims.</p>
<div class='row'>
{kpi_card('Groceries customers', N(groc['customers']))}
{kpi_card('Groceries spend', R(groc['spend']))}
{kpi_card('Groceries transactions', N(groc['transactions']))}
</div>
</div>

<div class='sec'>
<h2>Food Lovers Market — client-specific KPIs</h2>
<p class='sub'>Distinct FNB cardholders who transacted at <b>FOOD LOVERS MARKET</b> in the last 12 months.</p>
{grid_kpis(fl_market_row, 'Food Lovers Market')}
{f'''<div class='callout good'>Rank #{int(fl_market_row['spend_rank'])} in Groceries · {fl_market_row['penetration_pct']:.1f}% penetration · avg share of wallet {fl_market_row['avg_share_of_wallet']:.1f}%</div>''' if fl_market_row is not None else ''}
</div>

<div class='sec'>
<h2>Food Lovers Eatery — client-specific KPIs</h2>
<p class='sub'>Distinct FNB cardholders who transacted at <b>FOOD LOVERS EATERY</b> in the last 12 months. Separate merchant — smaller base but different value profile.</p>
{grid_kpis(fl_eatery_row, 'Food Lovers Eatery')}
{f'''<div class='callout good'>Rank #{int(fl_eatery_row['spend_rank'])} in Groceries · {fl_eatery_row['penetration_pct']:.1f}% penetration · avg share of wallet {fl_eatery_row['avg_share_of_wallet']:.1f}%</div>''' if fl_eatery_row is not None else ''}
</div>

<div class='sec'>
<h2>Food Lovers — combined (Market + Eatery)</h2>
<p class='sub'>Union of customer bases across BOTH DESTINATIONs, regardless of category (Market lives in Groceries, Eatery in a different category). Validated at generation time: primary count matched set-logic union within {delta_pct:.3f}%. Use if pitching the brand as a whole.</p>
{grid_kpis_combined()}
<p class='sub' style='font-size:.75rem;color:#94a3b8;margin-top:8px'>Overlap detail: {int(fl_validate['market_customers']):,} Market shoppers + {int(fl_validate['eatery_customers']):,} Eatery shoppers − {int(fl_validate['in_both']):,} in both = {int(fl_validate['true_union']):,} unique customers.</p>
</div>

<div class='sec'>
<h2>Competitive set — Groceries top 10</h2>
<p class='sub'>Food Lovers highlighted. Same data used in nav_dashboard.</p>
<div class='two-col'>
<div><h3 style='font-size:.9rem;color:#1e3a5f;margin-bottom:6px'>Total spend</h3><div class='chbox tall'><canvas id='chCompSpend'></canvas></div></div>
<div><h3 style='font-size:.9rem;color:#1e3a5f;margin-bottom:6px'>Spend per customer</h3><div class='chbox tall'><canvas id='chCompSpc'></canvas></div></div>
</div>
<table><tr><th>Retailer</th><th>Customers</th><th>Total Spend</th><th>Spend/Cust</th><th>Market Share</th></tr>
{comp_table_rows}
</table>
</div>

<div class='sec'>
<h2>Who shops at Food Lovers (combined) — demographics</h2>
<p class='sub'>Distinct customers who shopped at either Food Lovers Market or Eatery in the last 12 months.</p>
<div class='row'>
{demo_row}
</div>
</div>

<div class='sec'>
<h2>Income band × gender</h2>
<p class='sub'>Monthly income bands (as coded in <code>stg_customers.income_group</code>). Number of unique customers per (band, gender).</p>
<div class='chbox tall'><canvas id='chIncomeGender'></canvas></div>
</div>

<div class='sec'>
<h2>Age band × gender</h2>
<div class='chbox tall'><canvas id='chAgeGender'></canvas></div>
</div>

<div class='sec'>
<h2>Provincial spend (top 8)</h2>
<div class='chbox tall'><canvas id='chGeo'></canvas></div>
</div>

</div>

<script>
const Data = {json.dumps(data_obj)};
const colors = {{
    male:   '#2E75B6',
    female: '#E85C0D',
    accent: '#1e3a5f',
    accent2:'#0f172a',
    fl:     '#f59e0b',
}};

function mkChart(id, cfg) {{
    const el = document.getElementById(id);
    if (!el) return;
    new Chart(el, cfg);
}}

// Competitor total spend (horizontal bar so labels fit)
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

// Income band × gender (grouped bar)
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
</script>

</body></html>
"""

OUT = 'food_lovers_pitch.html'
with open(OUT, 'w') as f:
    f.write(html)

print()
print(f'Wrote: {OUT}')
print('Open in browser and screenshot each section into slides.')
