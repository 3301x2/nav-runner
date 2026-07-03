#!/usr/bin/env python3
"""
Analyse the Audience_Unpack_Vox.xlsx workbook from Suzanne.

Purpose: figure out what columns / value spaces / pivot logic are in the
workbook so we can:
  1. Map the fields we DON'T have in our BQ data (RETAIL_MODEL, MOB tenure,
     account count) back to something we could reproduce or request access to
  2. Understand the pivot definitions ("SPECIFIC BUCKETS REQUESTED",
     "AGREEMENTS MORE THAN 3 YEARS") so we can replicate them
  3. Compare Suzanne's audience sizing against our own numbers

Reads: every sheet, every column, every distinct value (capped).
Writes: nothing — pure report to stdout.

Usage:
    python3 scripts/analyse_vox_audience_xlsx.py [path/to/Audience_Unpack_Vox.xlsx]

If no path given, looks for the file in ~/Downloads with common names.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas is required. Install with: pip3 install pandas openpyxl")

try:
    import openpyxl  # noqa: F401
except ImportError:
    sys.exit("openpyxl is required. Install with: pip3 install openpyxl")


# ── Locate the file ──────────────────────────────────────────────────────
def find_workbook() -> Path:
    if len(sys.argv) > 1:
        p = Path(sys.argv[1]).expanduser()
        if not p.exists():
            sys.exit(f'File not found: {p}')
        return p

    candidates = [
        '~/Downloads/Audience_Unpack_Vox.xlsx',
        '~/Downloads/audience_unpack_vox.xlsx',
        '~/Downloads/Audience_Unpack_VOX.xlsx',
        '~/Downloads/Audience Unpack Vox.xlsx',
    ]
    for c in candidates:
        p = Path(c).expanduser()
        if p.exists():
            return p

    # Fallback: any file in Downloads with 'vox' + 'audience' in the name
    downloads = Path('~/Downloads').expanduser()
    if downloads.exists():
        for f in downloads.glob('*.xlsx'):
            n = f.name.lower()
            if 'vox' in n and 'audience' in n:
                return f
            if 'vox' in n and 'unpack' in n:
                return f

    sys.exit('Could not find Audience_Unpack_Vox.xlsx. Pass the path as arg 1.')


workbook_path = find_workbook()
print(f'📂 Reading: {workbook_path}')
print(f'   Size: {workbook_path.stat().st_size / 1024:.1f} KB')
print()


# ── Load all sheets ──────────────────────────────────────────────────────
xl = pd.ExcelFile(workbook_path)
print(f'📑 Found {len(xl.sheet_names)} sheet(s):')
for i, name in enumerate(xl.sheet_names):
    print(f'   {i+1}. {name!r}')
print()


# ── Per-sheet inspection ─────────────────────────────────────────────────
DIVIDER = '─' * 78


def summarize_sheet(name: str) -> None:
    print(DIVIDER)
    print(f'🔍 Sheet: {name!r}')
    print(DIVIDER)

    # Try a couple of common header rows — pivot sheets sometimes have
    # blank rows before the header
    df = None
    used_header = None
    for header_row in (0, 1, 2, 3):
        try:
            candidate = pd.read_excel(xl, sheet_name=name, header=header_row)
            # Prefer a header row where we get named columns, not "Unnamed: 0"
            unnamed_ratio = sum(
                1 for c in candidate.columns if str(c).startswith('Unnamed')
            ) / max(len(candidate.columns), 1)
            if unnamed_ratio < 0.5 and len(candidate.columns) > 1:
                df = candidate
                used_header = header_row
                break
        except Exception:
            continue

    if df is None:
        # Give up and take the raw grid
        df = pd.read_excel(xl, sheet_name=name, header=None)
        used_header = None
        print(f'   ⚠ No clean header found — showing raw grid')

    print(f'   Shape:      {df.shape[0]:,} rows × {df.shape[1]} columns')
    if used_header is not None:
        print(f'   Header row: {used_header}')

    print()
    print('   COLUMNS:')
    for col in df.columns:
        dtype = df[col].dtype
        non_null = df[col].notna().sum()
        distinct = df[col].nunique(dropna=True)
        print(f'     • {col!r:<45} {str(dtype):<12} {non_null:>7,} non-null | {distinct:>6,} distinct')

    print()
    print('   DISTINCT VALUES per column (up to 15 shown):')
    for col in df.columns:
        vals = df[col].dropna().unique()
        distinct = len(vals)
        if distinct == 0:
            print(f'     • {col!r}: (all null)')
            continue
        show = vals[:15]
        rendered = ', '.join(repr(v) for v in show)
        more = f'  … (+{distinct - 15} more)' if distinct > 15 else ''
        print(f'     • {col!r}:')
        print(f'         {rendered}{more}')

    print()
    print('   FIRST 5 ROWS (raw):')
    with pd.option_context('display.max_columns', None,
                           'display.width', 200,
                           'display.max_colwidth', 30):
        print(df.head(5).to_string(index=False))
    print()


for sheet_name in xl.sheet_names:
    summarize_sheet(sheet_name)


# ── Summary of what we care about ────────────────────────────────────────
print(DIVIDER)
print('🎯 KEY LOOKUPS — for the Adidas / Superbalist grid work')
print(DIVIDER)

target_columns = {
    'RETAIL_MODEL':   'Pierre\'s question — the wealth-tier code column',
    'RISK_CLASS':     'Credit risk classification',
    'MOB':            'Months on Book (account tenure)',
    'age_band_acct':  'Age of account',
    'age_band_cust':  'Age of customer',
    'age_band_cost':  '?',
    'gender':         'Gender',
    'marital_status': 'Marital status',
    'NR_ACCOUNTS':    'Number of accounts',
    'initial_band':   '?',
    'AGREEMENT':      'Agreement/product context',
}

for sheet_name in xl.sheet_names:
    df = pd.read_excel(xl, sheet_name=sheet_name)
    matched = [c for c in df.columns if str(c).upper() in {k.upper() for k in target_columns}]
    if matched:
        print(f'\n   Sheet {sheet_name!r} contains {len(matched)} of the key columns:')
        for c in matched:
            key = next(k for k in target_columns if k.upper() == str(c).upper())
            print(f'     ✓ {c} — {target_columns[key]}')

print()
print(DIVIDER)
print('Done. Screenshot / paste the output back so we can build the mapping.')
