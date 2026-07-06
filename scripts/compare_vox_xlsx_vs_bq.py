#!/usr/bin/env python3
"""
Side-by-side comparison of the Audience_Unpack_Vox.xlsx workbook against
our BQ staging tables (stg_customers + stg_transactions) — with a bonus
schema-only peek at customer_spend.base_data to confirm nothing lives
there that stg_customers doesn't surface.

Purpose: figure out which Excel columns correspond to which BQ columns,
whether any identifier survives in the Excel that would let us join back
to UNIQUE_ID, and whether the Excel is aggregated or record-level.

Output is deliberately compact so 2-3 screenshots capture everything.

Usage:
    python3 scripts/compare_vox_xlsx_vs_bq.py [sandbox|production] [path/to/Audience_Unpack_Vox.xlsx]

If the xlsx path is omitted, searches ~/Downloads for a matching file.
"""
from __future__ import annotations
import os
import sys
import subprocess
from pathlib import Path


# ── Auto-install deps ────────────────────────────────────────────────────
REQUIRED = {
    'pandas':               'pandas',
    'openpyxl':             'openpyxl',
    'db_dtypes':            'db-dtypes',
    'google.cloud.bigquery':'google-cloud-bigquery',
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


# ── Parse args ───────────────────────────────────────────────────────────
ENV = sys.argv[1] if len(sys.argv) > 1 else 'sandbox'
PROJECT_MAP = {
    'sandbox': 'fmn-sandbox', 'dev': 'fmn-sandbox', 'sb': 'fmn-sandbox',
    'production': 'fmn-production-462814', 'prod': 'fmn-production-462814', 'prd': 'fmn-production-462814',
}
if ENV not in PROJECT_MAP:
    sys.exit(f'Usage: python3 {sys.argv[0]} [sandbox|production] [xlsx_path]')
PROJECT = PROJECT_MAP[ENV]


def find_workbook() -> Path:
    if len(sys.argv) > 2:
        p = Path(sys.argv[2]).expanduser()
        if not p.exists():
            sys.exit(f'File not found: {p}')
        return p
    downloads = Path('~/Downloads').expanduser()
    for f in downloads.glob('*.xlsx'):
        n = f.name.lower()
        if 'vox' in n and ('audience' in n or 'unpack' in n):
            return f
    sys.exit('Could not find Audience_Unpack_Vox.xlsx. Pass the path as arg 2.')


workbook_path = find_workbook()


# ── Helpers ──────────────────────────────────────────────────────────────
DIV = '─' * 78
DIV2 = '═' * 78
MAX_DISTINCT_SHOWN = 15


def head(title: str) -> None:
    print()
    print(DIV2)
    print(f'  {title}')
    print(DIV2)


def sub(title: str) -> None:
    print()
    print(DIV)
    print(f'  {title}')
    print(DIV)


def show_distincts(name: str, series: pd.Series) -> None:
    vals = series.dropna().unique()
    total = len(vals)
    show = list(vals[:MAX_DISTINCT_SHOWN])
    rendered = ', '.join(str(v) for v in show)
    more = f'  … (+{total - MAX_DISTINCT_SHOWN} more)' if total > MAX_DISTINCT_SHOWN else ''
    print(f'     {name:<30} {total:>6} distinct | {rendered}{more}')


# ── EXCEL side ───────────────────────────────────────────────────────────
head(f'EXCEL: {workbook_path.name}')
print(f'  Size: {workbook_path.stat().st_size / 1024:.1f} KB')

# Try to detect hidden sheets via openpyxl (pd.ExcelFile doesn't distinguish)
import openpyxl
wb = openpyxl.load_workbook(workbook_path, read_only=False, data_only=True)
print(f'  Sheets (openpyxl): {wb.sheetnames}')
hidden = [s.title for s in wb.worksheets if s.sheet_state != 'visible']
if hidden:
    print(f'  🔎 HIDDEN sheets found: {hidden}')

# Also look for defined names (named ranges — often used to point at raw data)
if wb.defined_names:
    print(f'  🔎 Named ranges: {list(wb.defined_names)}')

xl = pd.ExcelFile(workbook_path)
excel_columns_all = set()

for sheet_name in xl.sheet_names:
    sub(f'Sheet: {sheet_name!r}')
    # Try a few header rows for messy pivots
    df = None
    for header_row in (0, 1, 2, 3):
        try:
            candidate = pd.read_excel(xl, sheet_name=sheet_name, header=header_row)
            unnamed = sum(1 for c in candidate.columns if str(c).startswith('Unnamed'))
            if unnamed / max(len(candidate.columns), 1) < 0.5:
                df = candidate
                break
        except Exception:
            continue
    if df is None:
        df = pd.read_excel(xl, sheet_name=sheet_name, header=None)

    print(f'  Shape: {df.shape[0]:,} rows × {df.shape[1]} cols')

    # Detect if the sheet looks aggregated (NR_ACCOUNTS or similar sum column)
    sum_cols = [c for c in df.columns if any(k in str(c).upper()
                for k in ('NR_ACCOUNT', 'SUM', 'TOTAL', 'COUNT'))]
    if sum_cols:
        print(f'  ⚠  Aggregation columns present: {sum_cols}')

    # Check for identifier-looking columns
    id_cols = [c for c in df.columns if any(k in str(c).upper()
               for k in ('UNIQUE_ID', 'CIF', 'CUST_ID', 'CUSTOMER_ID',
                         'ACCOUNT_NR', 'ACCT_NR', 'HASH'))]
    if id_cols:
        print(f'  🎯 IDENTIFIER-shaped columns: {id_cols}')

    print('\n  DISTINCT VALUES per column (up to 15 shown):')
    for col in df.columns:
        excel_columns_all.add(str(col))
        try:
            show_distincts(str(col), df[col])
        except Exception as e:
            print(f'     {col!r}: (error: {e})')


# ── BQ side ──────────────────────────────────────────────────────────────
head(f'BQ STAGING: {PROJECT}.staging')
bq = bigquery.Client(project=PROJECT)


def show_bq_schema(dataset: str, table: str, sample_distinct_cols: list[str] | None = None) -> list[str]:
    """Returns list of column names, prints schema + selected distinct value counts."""
    fqn = f'{PROJECT}.{dataset}.{table}'
    sub(f'Table: {fqn}')

    schema_sql = f"""
        SELECT column_name, data_type
        FROM `{PROJECT}.{dataset}.INFORMATION_SCHEMA.COLUMNS`
        WHERE table_name = '{table}'
        ORDER BY ordinal_position
    """
    schema = list(bq.query(schema_sql).result())
    col_names = [r['column_name'] for r in schema]

    print(f'  {len(col_names)} columns:')
    for r in schema:
        print(f'     {r["column_name"]:<30} {r["data_type"]}')

    # Row count
    count_sql = f'SELECT COUNT(*) AS c FROM `{fqn}`'
    row_count = list(bq.query(count_sql).result())[0]['c']
    print(f'\n  Row count: {row_count:,}')

    if sample_distinct_cols:
        print('\n  DISTINCT VALUES per selected column (up to 15 shown):')
        for c in sample_distinct_cols:
            if c not in col_names:
                continue
            try:
                q = f"""
                    SELECT DISTINCT {c} AS v, COUNT(*) OVER () AS total_distinct
                    FROM `{fqn}`
                    WHERE {c} IS NOT NULL
                    LIMIT {MAX_DISTINCT_SHOWN}
                """
                rows = list(bq.query(q).result())
                if not rows:
                    print(f'     {c:<30} (all null)')
                    continue
                total = rows[0]['total_distinct']
                vals = [str(r['v']) for r in rows]
                more = f'  … (+{total - len(vals)} more)' if total > len(vals) else ''
                print(f'     {c:<30} {total:>6} distinct | {", ".join(vals)}{more}')
            except Exception as e:
                print(f'     {c:<30} (error: {e})')

    return col_names


stg_customers_cols = show_bq_schema(
    'staging', 'stg_customers',
    sample_distinct_cols=[
        'gender_label', 'income_segment', 'hyper_segment', 'income_group',
        'credit_risk_class', 'main_banked', 'age_group', 'profile_age',
    ],
)

stg_transactions_cols = show_bq_schema(
    'staging', 'stg_transactions',
    sample_distinct_cols=['CATEGORY_ONE', 'CATEGORY_TWO', 'NAV_CATEGORY', 'PROVINCE'],
)


# ── base_data schema only (confirm nothing extra hides there) ────────────
head(f'BQ SOURCE: {PROJECT}.customer_spend.base_data (schema-only)')
try:
    base_schema_sql = f"""
        SELECT column_name, data_type
        FROM `{PROJECT}.customer_spend.INFORMATION_SCHEMA.COLUMNS`
        WHERE table_name = 'base_data'
        ORDER BY ordinal_position
    """
    base_cols = [(r['column_name'], r['data_type']) for r in bq.query(base_schema_sql).result()]
    print(f'  {len(base_cols)} columns:')
    for name, dtype in base_cols:
        surfaced = '  ← in stg_customers' if name in stg_customers_cols else ''
        print(f'     {name:<30} {dtype:<12}{surfaced}')
    only_in_base = [n for n, _ in base_cols if n not in stg_customers_cols and n != 'month']
    if only_in_base:
        print(f'\n  ⚠  Columns in base_data NOT surfaced in stg_customers: {only_in_base}')
    else:
        print('\n  ✓ Everything from base_data is already in stg_customers.')
except Exception as e:
    print(f'  (error reading base_data schema: {e})')


# ── Column overlap ───────────────────────────────────────────────────────
head('OVERLAP — column-name matches (case-insensitive substring)')
bq_all = set(stg_customers_cols) | set(stg_transactions_cols)
matches = []
for xc in sorted(excel_columns_all):
    xc_up = str(xc).upper()
    for bc in bq_all:
        bc_up = bc.upper()
        # Exact match
        if xc_up == bc_up:
            matches.append((xc, bc, 'exact'))
            continue
        # Substring match either direction
        if len(xc_up) >= 4 and (xc_up in bc_up or bc_up in xc_up):
            matches.append((xc, bc, 'partial'))

if matches:
    print(f'  {len(matches)} candidate matches:\n')
    for xc, bc, kind in matches:
        print(f'     {xc:<25} ≈ {bc:<25} ({kind})')
else:
    print('  No obvious column-name overlaps found.')

print()
print(DIV2)
print('  Done. Screenshot each section back for mapping decisions.')
print(DIV2)
