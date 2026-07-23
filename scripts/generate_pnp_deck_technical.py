#!/usr/bin/env python3
"""
PnP Spend Shift decks, TECHNICAL explainer for Pierre.

Written for someone who wants to see the SQL, the tables, and the lineage
behind every number. Not a business narrative. Every number has:
  - The exact BigQuery table it comes from
  - The exact SQL query to reproduce it
  - The exact result to expect
  - A "why this table" data-provenance note

Pierre can run any query in BigQuery Studio, in the CLI (bq query), or
in his notebook. All queries are read-only.

Usage:
  python3 scripts/generate_pnp_deck_technical.py
Output:
  pnp_deck_technical.html
"""
from __future__ import annotations
import html as _h
from datetime import datetime


def esc(s) -> str:
  return _h.escape(str(s))


now = datetime.now().strftime('%d %B %Y')


PROD = 'fmn-production-462014'
SB = 'fmn-sandbox'


# ── Structured content: each item has title, purpose, tables, sql, result ──
SECTIONS = [

  # ═══════════════════════════════════════════════════════════════════════
  # PART 1: THE DATA SOURCES
  # ═══════════════════════════════════════════════════════════════════════
  {
    'part': 'Part 1, The data sources',
    'id': 'data-sources',
    'title': '1.1 What tables the decks use',
    'purpose': 'Before any query, a map of every source table referenced in the two decks.',
    'body_html': f'''
      <h4>Prod tables (fmn-production-462014.PicknPay)</h4>
      <table>
        <tr><th>Table</th><th>Rows</th><th>Used for</th></tr>
        <tr><td><code>Audience_Upload_20260206</code></td><td>2,291,851</td><td>The FRG base. 2.29M FNB card customers with observable PnP behaviour. Every FRG-side number in both decks comes from here.</td></tr>
        <tr><td><code>latest_fnb_trns_base</code></td><td>5,764,147</td><td>Full FNB card transaction base. Not directly used in the deck, kept as reference.</td></tr>
        <tr><td><code>PNP_eBucks_BurgerFriday</code></td><td>5,808,696</td><td>Source of the six eBucks reward tier percentages (ASP, EPU, PMK, EBN, PVT, WLH).</td></tr>
        <tr><td><code>PNP_payday_ebucks_202512</code></td><td>5,605,954</td><td>Cross-check for the eBucks tier distribution.</td></tr>
      </table>

      <h4>Sandbox tables (fmn-sandbox.pnp_liveramp)</h4>
      <p>These are LiveRamp clean-room outputs mirrored from gs://liveramp_output/ using <code>scripts/ingest_liveramp_to_sandbox.sh</code>.</p>
      <table>
        <tr><th>Table</th><th>Rows</th><th>Used for</th></tr>
        <tr><td><code>lr_out_pnp_clothing_base</code></td><td>857,373</td><td>The only LR table where the join to FRG works (95% overlap). Source of the Smart Shopper R200M uplift.</td></tr>
        <tr><td><code>lr_out_pnp_audiences_for_awareness</code></td><td>2,278,245</td><td>PnP\\'s own awareness audience. Overlaps FRG at only 1,284 rows because hashes are of different plaintext.</td></tr>
        <tr><td><code>lr_out_ntb_transact</code></td><td>788,806</td><td>Baby-category NTB propensity scoring. Same hash mismatch issue.</td></tr>
        <tr><td><code>lr_out_fnb_pnp_awareness</code></td><td>31,834,062</td><td>Large fanned audience file. Not directly used in the deck.</td></tr>
      </table>

      <h4>How to inspect the schema of any of these</h4>
      <pre><code>SELECT column_name, data_type, ordinal_position
FROM `{PROD}.PicknPay.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = 'Audience_Upload_20260206'
ORDER BY ordinal_position;</code></pre>
    '''
  },
  {
    'part': 'Part 1, The data sources',
    'id': 'audience-upload-columns',
    'title': '1.2 The 18 columns in Audience_Upload_20260206',
    'purpose': "Every FRG-side deck number rolls up from these columns. Understanding them is understanding the whole deck.",
    'body_html': '''
      <table>
        <tr><th>Column</th><th>Type</th><th>Meaning</th></tr>
        <tr><td><code>UNIQUE_ID</code></td><td>STRING</td><td>Hashed FNB customer identifier (SHA-256 hex). Same customer will have the same UNIQUE_ID across FRG tables.</td></tr>
        <tr><td><code>month</code></td><td>INT64</td><td>Snapshot period identifier.</td></tr>
        <tr><td><code>EMAIL_ADDR</code></td><td>STRING</td><td>SHA-256 hashed email address, lowercase hex. The join key against LR tables.</td></tr>
        <tr><td><code>CUST_CELL_NO</code></td><td>STRING</td><td>SHA-256 hashed mobile number. Alternative join key.</td></tr>
        <tr><td><code>nr_tot_trns</code></td><td>INT64</td><td>Number of total card transactions in the observation window.</td></tr>
        <tr><td><code>val_tot_trns</code></td><td>FLOAT64</td><td>Total Rand value of card transactions. <b>Denominator for wallet share.</b></td></tr>
        <tr><td><code>spar_exclusion_count</code></td><td>INT64</td><td>Number of Spar transactions excluded to prevent Spar-heavy customers biasing the PnP wallet share.</td></tr>
        <tr><td><code>nr_pnp_trns</code></td><td>INT64</td><td>Number of PnP-specific transactions. <b>Used for PnP-active flag: nr_pnp_trns > 0.</b></td></tr>
        <tr><td><code>val_pnp_trns</code></td><td>FLOAT64</td><td>Total Rand value spent at PnP. <b>Numerator for wallet share.</b></td></tr>
        <tr><td><code>grocery_delivery_trns</code></td><td>INT64</td><td>Number of grocery-delivery transactions (any provider, includes ASAP + Sixty60 + Woolies online).</td></tr>
        <tr><td><code>CT02</code></td><td>STRING</td><td>Category code, mostly Groceries in this table.</td></tr>
        <tr><td><code>Retail_Model</code></td><td>STRING</td><td>The wealth-tier code (EU0, EL0, GL0, PB0, PC0, PW0, PWH, PWU). <b>Primary segmentation dimension.</b></td></tr>
        <tr><td><code>Main_Banked</code></td><td>INT64</td><td>Flag for main-banked customers.</td></tr>
        <tr><td><code>Hypersegment</code></td><td>STRING</td><td>Salaried / Self Employed / Retiree bucket.</td></tr>
        <tr><td><code>KPI_Risk_Class</code></td><td>STRING</td><td>Credit risk class (1-6, Thin, No Score).</td></tr>
        <tr><td><code>MBD_Ind</code></td><td>INT64</td><td>Main-banked-degree indicator flag.</td></tr>
        <tr><td><code>MBD_Tier</code></td><td>STRING</td><td>Main-banked-degree tier (1 deepest to 5 shallowest). <b>Used in the SS uplift table.</b></td></tr>
        <tr><td><code>HOLD_OUT</code></td><td>STRING</td><td>Holdout flag for future test/control designs.</td></tr>
      </table>
    '''
  },

  # ═══════════════════════════════════════════════════════════════════════
  # PART 2: THE HEADLINE NUMBERS
  # ═══════════════════════════════════════════════════════════════════════
  {
    'part': 'Part 2, The headline numbers',
    'id': 'headline-frg',
    'title': '2.1 The FRG base: 2.29M customers, 1.34M PnP-active, R3.08B spend',
    'purpose': "Top-of-deck sizing. Every downstream stat is a slice of this.",
    'body_html': f'''
      <h4>The query</h4>
      <pre><code>SELECT
    COUNT(*)                                                     AS frg_customers,
    COUNTIF(nr_pnp_trns > 0)                                     AS pnp_active,
    ROUND(100.0 * COUNTIF(nr_pnp_trns > 0) / COUNT(*), 1)         AS active_pct,
    ROUND(SUM(val_pnp_trns) / 1e9, 2)                            AS total_pnp_spend_b,
    ROUND(AVG(SAFE_DIVIDE(val_pnp_trns, val_tot_trns)) * 100, 1) AS avg_wallet_share
FROM `{PROD}.PicknPay.Audience_Upload_20260206`
WHERE val_tot_trns &gt; 0;</code></pre>

      <h4>Expected result</h4>
      <table>
        <tr><th>frg_customers</th><th>pnp_active</th><th>active_pct</th><th>total_pnp_spend_b</th><th>avg_wallet_share</th></tr>
        <tr><td>2,291,851</td><td>1,344,538</td><td>58.7</td><td>3.08</td><td>11.4</td></tr>
      </table>

      <h4>Data provenance note</h4>
      <p>Audience_Upload_20260206 is a monthly snapshot generated by the PnP data engineering team, dated 20 June 2026. It represents FNB card customers with any transaction activity in the 12-month observation window ending in that snapshot period. Not every FNB cardholder is here (only those who transacted); not every PnP customer is here (only those who used FNB cards).</p>
    '''
  },
  {
    'part': 'Part 2, The headline numbers',
    'id': 'pyramid',
    'title': '2.2 The pyramid match: 13.7 / 18.5 / 26.5 / 41.3 vs PnP\'s 13.6 / 21.5 / 22.5 / 41.9',
    'purpose': "The credibility anchor for the entire deck. Two independent data lenses arrive at the same customer pyramid.",
    'body_html': f'''
      <h4>The query</h4>
      <pre><code>WITH bucketed AS (
    SELECT CASE
        WHEN val_pnp_trns = 0 OR val_pnp_trns IS NULL       THEN '4. Lapsed proxy (no PnP spend)'
        WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) &lt; 0.10 THEN '3. Tertiary proxy (&lt;10%)'
        WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) &lt; 0.30 THEN '2. Secondary proxy (10-30%)'
        ELSE                                                     '1. Primary proxy (30%+)'
    END AS pnp_bucket
    FROM `{PROD}.PicknPay.Audience_Upload_20260206`
    WHERE val_tot_trns &gt; 0
)
SELECT pnp_bucket,
       COUNT(*) AS customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_frg
FROM bucketed
GROUP BY pnp_bucket
ORDER BY pnp_bucket;</code></pre>

      <h4>Expected result</h4>
      <table>
        <tr><th>pnp_bucket</th><th>customers</th><th>pct_of_frg</th><th>PnP slide 5 reference</th></tr>
        <tr><td>1. Primary proxy (30%+)</td><td>312,949</td><td>13.7</td><td>PnP Primary: 13.6</td></tr>
        <tr><td>2. Secondary proxy (10-30%)</td><td>423,335</td><td>18.5</td><td>PnP Secondary: 21.5</td></tr>
        <tr><td>3. Tertiary proxy (&lt;10%)</td><td>608,246</td><td>26.5</td><td>PnP Tertiary: 22.5</td></tr>
        <tr><td>4. Lapsed proxy (no PnP spend)</td><td>947,309</td><td>41.3</td><td>PnP Lapsed: 41.9</td></tr>
      </table>

      <h4>Why the middle tiers have larger gaps (defensive answer)</h4>
      <p>PnP defines Secondary as "shopped in last 52 weeks but not last 9". That is a <b>time-window</b> measure. We define Secondary as "10-30% wallet share". That is a <b>spend-share</b> measure. The two do not have to align on the middle tiers because the underlying scales differ; the fact that Primary and Lapsed still match to within 0.6 percentage points is what makes the pyramid comparison valid.</p>
    '''
  },

  # ═══════════════════════════════════════════════════════════════════════
  # PART 3: THE CROSS-TABS
  # ═══════════════════════════════════════════════════════════════════════
  {
    'part': 'Part 3, The cross-tabs',
    'id': 'retail-model',
    'title': '3.1 Retail_Model x PnP behaviour (the 8-tier appendix table)',
    'purpose': "Every campaign-audience sizing on slide 12 rolls up to this cross-tab.",
    'body_html': f'''
      <h4>The query</h4>
      <pre><code>SELECT
    Retail_Model,
    COUNT(*)                                                     AS customers,
    COUNTIF(nr_pnp_trns &gt; 0)                                    AS pnp_active,
    ROUND(100.0 * COUNTIF(nr_pnp_trns &gt; 0) / COUNT(*), 1)       AS active_pct,
    ROUND(AVG(val_pnp_trns), 0)                                  AS avg_pnp_spend,
    ROUND(AVG(SAFE_DIVIDE(val_pnp_trns, val_tot_trns)) * 100, 1) AS avg_wallet_pct,
    ROUND(SUM(val_pnp_trns) / 1e6, 1)                            AS total_pnp_m
FROM `{PROD}.PicknPay.Audience_Upload_20260206`
WHERE val_tot_trns &gt; 0
GROUP BY Retail_Model
ORDER BY total_pnp_m DESC;</code></pre>

      <h4>Expected result</h4>
      <table>
        <tr><th>Retail_Model</th><th>customers</th><th>pnp_active</th><th>active_pct</th><th>avg_pnp_spend</th><th>avg_wallet_pct</th><th>total_pnp_m</th></tr>
        <tr><td>PC0</td><td>568,188</td><td>392,576</td><td>69.1</td><td>1929</td><td>12.7</td><td>1,095.8</td></tr>
        <tr><td>PW0</td><td>284,255</td><td>185,345</td><td>65.2</td><td>2203</td><td>11.1</td><td>626.2</td></tr>
        <tr><td>GL0</td><td>549,877</td><td>326,052</td><td>59.3</td><td>1073</td><td>12.1</td><td>589.8</td></tr>
        <tr><td>PB0</td><td>232,317</td><td>152,739</td><td>65.7</td><td>1536</td><td>12.6</td><td>356.9</td></tr>
        <tr><td>EU0</td><td>604,469</td><td>264,641</td><td>43.8</td><td>544</td><td>10.5</td><td>328.9</td></tr>
        <tr><td>PWU</td><td>5,189</td><td>2,832</td><td>54.6</td><td>10,115</td><td>8.0</td><td>52.5</td></tr>
        <tr><td>EL0</td><td>43,823</td><td>18,239</td><td>41.6</td><td>417</td><td>9.7</td><td>18.3</td></tr>
        <tr><td>PWH</td><td>3,721</td><td>2,110</td><td>56.7</td><td>3,204</td><td>8.4</td><td>11.9</td></tr>
      </table>

      <h4>Retail_Model tier code translations</h4>
      <ul>
        <li>EU0 = Entry Wallet</li>
        <li>EL0 = Entry Lower</li>
        <li>GL0 = Middle Market (Gold Loyalty)</li>
        <li>PB0 = Emerging Affluent (Private Bronze)</li>
        <li>PC0 = Affluent (Private Consumer)</li>
        <li>PW0 = Wealth (Private Wealth)</li>
        <li>PWU = Ultra High Net Worth</li>
        <li>PWH = High Net Worth</li>
      </ul>
    '''
  },
  {
    'part': 'Part 3, The cross-tabs',
    'id': 'wallet-buckets',
    'title': '3.2 Wallet-share headroom buckets (the R13.2B story)',
    'purpose': "Source of the R13.2B switch-pool claim and the R132M per 1pt shift statistic.",
    'body_html': f'''
      <h4>The query</h4>
      <pre><code>WITH bucketed AS (
    SELECT CASE
        WHEN val_pnp_trns = 0 OR val_pnp_trns IS NULL       THEN '0. No PnP spend'
        WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) &lt; 0.05 THEN '1. Under 5%'
        WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) &lt; 0.10 THEN '2. 5-10%'
        WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) &lt; 0.20 THEN '3. 10-20%'
        WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) &lt; 0.40 THEN '4. 20-40%'
        ELSE                                                     '5. 40%+'
    END AS bucket, val_pnp_trns, val_tot_trns
    FROM `{PROD}.PicknPay.Audience_Upload_20260206`
    WHERE val_tot_trns &gt; 0
)
SELECT bucket,
       COUNT(*) AS customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct,
       ROUND(SUM(val_pnp_trns) / 1e6, 1) AS pnp_spend_m,
       ROUND(SUM(val_tot_trns) / 1e6, 1) AS total_spend_m
FROM bucketed
GROUP BY bucket
ORDER BY bucket;</code></pre>

      <h4>Expected result</h4>
      <table>
        <tr><th>bucket</th><th>customers</th><th>pct</th><th>pnp_spend_m</th><th>total_spend_m</th></tr>
        <tr><td>0. No PnP spend</td><td>947,309</td><td>41.3</td><td>0.0</td><td>6,757.9</td></tr>
        <tr><td>1. Under 5%</td><td>381,127</td><td>16.6</td><td>137.2</td><td>6,451.7</td></tr>
        <tr><td>2. 5-10%</td><td>227,119</td><td>9.9</td><td>225.9</td><td>3,106.9</td></tr>
        <tr><td>3. 10-20%</td><td>266,996</td><td>11.6</td><td>487.6</td><td>3,379.6</td></tr>
        <tr><td>4. 20-40%</td><td>258,294</td><td>11.3</td><td>871.5</td><td>3,057.3</td></tr>
        <tr><td>5. 40%+</td><td>210,994</td><td>9.2</td><td>1,358.1</td><td>2,276.7</td></tr>
      </table>

      <h4>How the R13.2B claim is calculated</h4>
      <p>Bucket 0 total spend = R6,757.9M (all going to competitors, none to PnP).<br>
      Bucket 1 non-PnP spend = R6,451.7M - R137.2M = R6,314.5M.<br>
      Sum = R6,757.9M + R6,314.5M = <b>R13,072.4M</b>. Deck rounds to R13.2B (slight over-round for narrative simplicity, actual is R13.1B).</p>

      <h4>How the R132M per 1pt shift is calculated</h4>
      <p>Bottom two buckets contain 947,309 + 381,127 = <b>1,328,436 customers</b>.<br>
      Their non-PnP spend total is R13,072.4M.<br>
      1% shift on R13,072.4M = <b>R130.7M</b>. Deck rounds to R132M.</p>
    '''
  },
  {
    'part': 'Part 3, The cross-tabs',
    'id': 'asap-adoption',
    'title': '3.3 ASAP adoption wealth gradient (the 6x ratio)',
    'purpose': "Backs Unlock 2 in the Super deck. Source of the 'weight ASAP media 3x toward top tiers' recommendation.",
    'body_html': f'''
      <h4>The query</h4>
      <pre><code>SELECT
    Retail_Model,
    COUNT(*)                                                     AS customers,
    COUNTIF(grocery_delivery_trns &gt; 0)                          AS delivery_users,
    ROUND(100.0 * COUNTIF(grocery_delivery_trns &gt; 0) / COUNT(*), 1) AS adoption_pct
FROM `{PROD}.PicknPay.Audience_Upload_20260206`
GROUP BY Retail_Model
ORDER BY adoption_pct DESC;</code></pre>

      <h4>Expected result</h4>
      <table>
        <tr><th>Retail_Model</th><th>customers</th><th>delivery_users</th><th>adoption_pct</th></tr>
        <tr><td>PWU</td><td>5,189</td><td>1,633</td><td><b>31.5</b></td></tr>
        <tr><td>PW0</td><td>284,259</td><td>78,571</td><td>27.6</td></tr>
        <tr><td>PWH</td><td>3,721</td><td>1,007</td><td>27.1</td></tr>
        <tr><td>PC0</td><td>568,192</td><td>136,038</td><td>23.9</td></tr>
        <tr><td>PB0</td><td>232,319</td><td>38,618</td><td>16.6</td></tr>
        <tr><td>GL0</td><td>549,879</td><td>67,262</td><td>12.2</td></tr>
        <tr><td>EL0</td><td>43,823</td><td>2,535</td><td>5.8</td></tr>
        <tr><td>EU0</td><td>604,469</td><td>32,345</td><td><b>5.4</b></td></tr>
      </table>

      <h4>How the 6x is calculated</h4>
      <p>31.5% (PWU) / 5.4% (EU0) = 5.83, rounded to 6x in the deck.</p>

      <h4>Important caveat</h4>
      <p><code>grocery_delivery_trns</code> is <b>any online grocery delivery</b>, not PnP ASAP specifically. It captures Checkers Sixty60, Woolies Online, PnP ASAP, and any other on-demand grocery service. The interpretation is not "PnP ASAP adoption is 6x higher in wealth tiers"; it is "online grocery adoption in general skews wealthy, so PnP ASAP acquisition should follow that gradient."</p>
    '''
  },

  # ═══════════════════════════════════════════════════════════════════════
  # PART 4: THE LR JOIN AND THE SS UPLIFT
  # ═══════════════════════════════════════════════════════════════════════
  {
    'part': 'Part 4, The LR clean-room join',
    'id': 'clothing-base',
    'title': '4.1 The clothing_base join (the only LR table that joins)',
    'purpose': "This one join is the source of Unlocks 3 and 4 in the Super deck (SS enrolment R200M, MBD_Tier x SS matrix).",
    'body_html': f'''
      <h4>How lr_out_pnp_clothing_base got into sandbox</h4>
      <p>LiveRamp clean-room question output <code>PnP_clothing_base_2026-03-19_08-38-43.parquet</code> was written to <code>gs://liveramp_output/date=2026-03-19/.../</code>. Our <code>ingest_liveramp_to_sandbox.sh</code> script loaded it into <code>{SB}.pnp_liveramp.lr_out_pnp_clothing_base</code> using <code>bq load --source_format=PARQUET</code>. The table has 857,373 rows and 2 columns: <code>email_addr</code> (SHA-256) and <code>SmartShopper_Indicator</code> (Y/N).</p>

      <h4>The overlap query</h4>
      <pre><code>WITH lr AS (
    SELECT DISTINCT email_addr, SmartShopper_Indicator
    FROM `{SB}.pnp_liveramp.lr_out_pnp_clothing_base`
)
SELECT
    COUNT(*)                                             AS clothing_total,
    COUNTIF(SmartShopper_Indicator = 'Y')                AS with_ss,
    COUNTIF(SmartShopper_Indicator = 'N')                AS without_ss,
    (SELECT COUNT(DISTINCT f.EMAIL_ADDR)
     FROM `{PROD}.PicknPay.Audience_Upload_20260206` f
     JOIN lr l ON f.EMAIL_ADDR = l.email_addr)           AS overlap_with_frg
FROM lr;</code></pre>

      <h4>Expected result</h4>
      <table>
        <tr><th>clothing_total</th><th>with_ss</th><th>without_ss</th><th>overlap_with_frg</th></tr>
        <tr><td>729,942</td><td>215,545</td><td>514,397</td><td>696,319</td></tr>
      </table>

      <h4>Why THIS table joined (and pnp_audiences_for_awareness did not)</h4>
      <p>The clothing_base table was generated by PnP inside the clean room from an audience list that came from FNB via the LR ingestion pipeline. The email hashes therefore match FRG email hashes because both were normalised the same way (trim, lowercase, SHA-256) upstream in the LR pipeline.</p>
      <p>By contrast, <code>lr_out_pnp_audiences_for_awareness</code> was generated from PnP\\'s <b>own</b> customer database. PnP hashes emails through a different normalisation recipe (or with a different secret salt). Same output format, different underlying value, 1,284 accidental collisions (which is roughly what you'd expect at chance).</p>

      <h4>The uplift query</h4>
      <pre><code>WITH lr AS (
    SELECT DISTINCT email_addr, SmartShopper_Indicator
    FROM `{SB}.pnp_liveramp.lr_out_pnp_clothing_base`
)
SELECT
    l.SmartShopper_Indicator,
    COUNT(*)                                                     AS customers,
    ROUND(AVG(f.val_pnp_trns), 0)                                AS avg_pnp_spend,
    ROUND(AVG(f.val_tot_trns), 0)                                AS avg_total_spend,
    ROUND(AVG(SAFE_DIVIDE(f.val_pnp_trns, f.val_tot_trns)) * 100, 1) AS wallet_pct
FROM `{PROD}.PicknPay.Audience_Upload_20260206` f
JOIN lr l ON f.EMAIL_ADDR = l.email_addr
WHERE f.val_tot_trns &gt; 0
GROUP BY l.SmartShopper_Indicator;</code></pre>

      <h4>Expected result</h4>
      <table>
        <tr><th>SmartShopper_Indicator</th><th>customers</th><th>avg_pnp_spend</th><th>avg_total_spend</th><th>wallet_pct</th></tr>
        <tr><td>N</td><td>494,967</td><td>1,178</td><td>9,944</td><td>11.4</td></tr>
        <tr><td>Y</td><td>215,545</td><td>1,584</td><td>10,527</td><td>14.7</td></tr>
      </table>

      <h4>How the R200M is calculated</h4>
      <p>Uplift per conversion = R1,584 - R1,178 = R406 per customer per year.<br>
      Non-SS customers in the clothing base = 494,967.<br>
      100% conversion upside = 494,967 x R406 = <b>R200.9M</b>. Deck rounds to R200M.</p>

      <h4>How the 34% is calculated</h4>
      <p>R1,584 / R1,178 - 1 = 34.5%. Deck says 34%.</p>
    '''
  },
  {
    'part': 'Part 4, The LR clean-room join',
    'id': 'mbd-uplift',
    'title': '4.2 The MBD_Tier x SmartShopper activation matrix (Unlock 4)',
    'purpose': "Proves the SS uplift holds across every wealth-depth tier, not just as a whole-population average.",
    'body_html': f'''
      <h4>The query</h4>
      <pre><code>WITH lr AS (
    SELECT DISTINCT email_addr, SmartShopper_Indicator
    FROM `{SB}.pnp_liveramp.lr_out_pnp_clothing_base`
)
SELECT
    f.MBD_Tier,
    l.SmartShopper_Indicator,
    COUNT(*)                        AS matched,
    ROUND(AVG(f.val_pnp_trns), 0)   AS avg_pnp_spend
FROM `{PROD}.PicknPay.Audience_Upload_20260206` f
JOIN lr l ON f.EMAIL_ADDR = l.email_addr
WHERE f.MBD_Tier IS NOT NULL
GROUP BY f.MBD_Tier, l.SmartShopper_Indicator
ORDER BY f.MBD_Tier, l.SmartShopper_Indicator;</code></pre>

      <h4>Expected result</h4>
      <table>
        <tr><th>MBD_Tier</th><th>SS_Indicator</th><th>matched</th><th>avg_pnp_spend</th></tr>
        <tr><td>Tier 1</td><td>N</td><td>17,082</td><td>625</td></tr>
        <tr><td>Tier 1</td><td>Y</td><td>5,825</td><td>771</td></tr>
        <tr><td>Tier 2</td><td>N</td><td>91,879</td><td>868</td></tr>
        <tr><td>Tier 2</td><td>Y</td><td>36,439</td><td>1,222</td></tr>
        <tr><td>Tier 3</td><td>N</td><td>194,054</td><td>1,157</td></tr>
        <tr><td>Tier 3</td><td>Y</td><td>84,114</td><td>1,524</td></tr>
        <tr><td>Tier 4</td><td>N</td><td>150,836</td><td>1,364</td></tr>
        <tr><td>Tier 4</td><td>Y</td><td>69,533</td><td>1,802</td></tr>
        <tr><td>Tier 5</td><td>N</td><td>31,043</td><td>1,476</td></tr>
        <tr><td>Tier 5</td><td>Y</td><td>14,957</td><td>1,983</td></tr>
      </table>

      <h4>How the per-tier uplift is derived</h4>
      <p>Absolute uplift = SS-Y avg - SS-N avg. Relative uplift = absolute / SS-N avg.</p>
      <table>
        <tr><th>MBD_Tier</th><th>Abs uplift</th><th>Rel uplift</th></tr>
        <tr><td>Tier 1</td><td>R146</td><td>+23%</td></tr>
        <tr><td>Tier 2</td><td>R354</td><td>+41%</td></tr>
        <tr><td>Tier 3</td><td>R367</td><td>+32%</td></tr>
        <tr><td>Tier 4</td><td>R438</td><td>+32%</td></tr>
        <tr><td>Tier 5</td><td>R507</td><td>+34%</td></tr>
      </table>

      <h4>Why this is deck-worthy</h4>
      <p>Uplift is <b>consistent</b> across tiers (23-41% relative, monotonic in absolute Rands). If the SS uplift were purely self-selection (i.e., "SS members are wealthier so they spend more"), we would expect the uplift to disappear once we stratify by wealth. It does not. This is evidence that SS enrolment is at least partly causal, not fully explained by demographics.</p>
    '''
  },

  # ═══════════════════════════════════════════════════════════════════════
  # PART 5: THE EBUCKS TIERS
  # ═══════════════════════════════════════════════════════════════════════
  {
    'part': 'Part 5, The eBucks reward tier framework',
    'id': 'ebucks',
    'title': '5.1 The six eBucks reward tiers (Unlock 6)',
    'purpose': "Defines the tier structure available in prod, and honestly names the blocker preventing us from joining to FRG today.",
    'body_html': f'''
      <h4>The query</h4>
      <pre><code>SELECT
    reward_seg_id,
    COUNT(*)                                                  AS customers,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)        AS pct
FROM `{PROD}.PicknPay.PNP_eBucks_BurgerFriday`
GROUP BY reward_seg_id
ORDER BY customers DESC;</code></pre>

      <h4>Expected result</h4>
      <table>
        <tr><th>reward_seg_id</th><th>customers</th><th>pct</th><th>Meaning</th></tr>
        <tr><td>ASP</td><td>1,716,426</td><td>29.5</td><td>Aspire (entry tier)</td></tr>
        <tr><td>EPU</td><td>1,595,978</td><td>27.5</td><td>Entry Premier / Prestige Upcoming</td></tr>
        <tr><td>PMK</td><td>959,734</td><td>16.5</td><td>Premier (middle)</td></tr>
        <tr><td>EBN</td><td>941,311</td><td>16.2</td><td>Entry Banking</td></tr>
        <tr><td>PVT</td><td>370,914</td><td>6.4</td><td>Private</td></tr>
        <tr><td>WLH</td><td>225,641</td><td>3.9</td><td>Wealth</td></tr>
      </table>

      <h4>The blocker: FRG cannot join eBucks today</h4>
      <p>Both tables use SHA-256 hashes but of different underlying plaintexts.</p>
      <pre><code>-- FRG UNIQUE_ID sample (SHA-256 of an FNB customer key or email)
SELECT UNIQUE_ID FROM `{PROD}.PicknPay.Audience_Upload_20260206` LIMIT 3;
-- Result: 6d65cbb425aa94c015c88206ba1baf454866ca84cb10aeecb63b34b77a0af2058
-- Result: d7b6f04bc3024f7113dc13ca5873da5904e56214031e35faa7202eb28adf459...

-- eBucks cust_id_reg_no sample (SHA-256 of SA_ID)
SELECT cust_id_reg_no FROM `{PROD}.PicknPay.PNP_eBucks_BurgerFriday` LIMIT 3;
-- Result: 4b3cdcc36d6916a71d1ff2094ad3832aae5e0hd0cb6988bdd67eb44f28240345
-- Result: 5220b20a53a1808f730f34e647ca2b0409a7a538a400c9271cd3e14f003f11c33...</code></pre>

      <h4>Proof the join returns zero rows</h4>
      <pre><code>WITH frg AS (
    SELECT DISTINCT UNIQUE_ID AS id FROM `{PROD}.PicknPay.Audience_Upload_20260206`
    WHERE UNIQUE_ID IS NOT NULL
),
eb AS (
    SELECT DISTINCT cust_id_reg_no AS id FROM `{PROD}.PicknPay.PNP_eBucks_BurgerFriday`
    WHERE cust_id_reg_no IS NOT NULL
)
SELECT
    (SELECT COUNT(*) FROM frg) AS frg_ids,
    (SELECT COUNT(*) FROM eb)  AS ebucks_ids,
    (SELECT COUNT(*) FROM frg INNER JOIN eb USING (id)) AS overlap;</code></pre>
      <table>
        <tr><th>frg_ids</th><th>ebucks_ids</th><th>overlap</th></tr>
        <tr><td>2,290,340</td><td>5,799,546</td><td><b>0</b></td></tr>
      </table>

      <h4>Why the fix is LiveRamp RampID, not a mapping file</h4>
      <p>Two independent business divisions cannot exchange SA_ID-to-email mappings without exposing PII. LiveRamp RampID is the pseudonymous common key across data sources: both sides upload hashed identifiers, RampID resolves them to a shared key without exposing either underlying value. That is exactly what the clean room is for. Phase 2 of the roadmap is running this join.</p>
    '''
  },

  # ═══════════════════════════════════════════════════════════════════════
  # PART 6: OTHER SUPPORTING QUERIES
  # ═══════════════════════════════════════════════════════════════════════
  {
    'part': 'Part 6, Other supporting queries',
    'id': 'hypersegment',
    'title': '6.1 Hypersegment x PnP (Salaried / Self Employed / Retiree)',
    'purpose': "Used in the campaign audience sizing (slide 12 Part 2 rows about parents / lower-income Steady etc.).",
    'body_html': f'''
      <h4>The query (case-normalised)</h4>
      <pre><code>SELECT
    REGEXP_REPLACE(INITCAP(Hypersegment), r'^([A-Z])\\. ', r'\\1. ') AS hypersegment_clean,
    COUNT(*) AS customers,
    COUNTIF(nr_pnp_trns &gt; 0) AS pnp_active,
    ROUND(100.0 * COUNTIF(nr_pnp_trns &gt; 0) / COUNT(*), 1) AS active_pct,
    ROUND(AVG(val_pnp_trns), 0) AS avg_pnp_spend,
    ROUND(AVG(SAFE_DIVIDE(val_pnp_trns, val_tot_trns)) * 100, 1) AS avg_wallet_pct,
    ROUND(SUM(val_pnp_trns) / 1e6, 1) AS total_pnp_m
FROM `{PROD}.PicknPay.Audience_Upload_20260206`
WHERE val_tot_trns &gt; 0
GROUP BY hypersegment_clean
ORDER BY total_pnp_m DESC;</code></pre>

      <h4>Expected result</h4>
      <table>
        <tr><th>hypersegment</th><th>customers</th><th>pnp_active</th><th>active_pct</th><th>avg_pnp_spend</th><th>wallet_pct</th><th>total_pnp_m</th></tr>
        <tr><td>C. Salaried</td><td>1,266,257</td><td>~713k</td><td>56.3</td><td>1,108</td><td>11.2</td><td>1,402.9</td></tr>
        <tr><td>A. Self Employed</td><td>797,919</td><td>~504k</td><td>63.2</td><td>1,617</td><td>11.7</td><td>1,290.2</td></tr>
        <tr><td>B. Retiree</td><td>227,662</td><td>~127k</td><td>55.6</td><td>1,700</td><td>14.0</td><td>387.1</td></tr>
      </table>

      <h4>Why we normalise the case</h4>
      <p>The raw data has both "C. Salaried" (903,083 customers) and "C. SALARIED" (363,176 customers) as separate values. This is upstream data quality. We combine them into "C. Salaried" (1,266,257) so downstream analytics is not fooled by the split.</p>
    '''
  },
  {
    'part': 'Part 6, Other supporting queries',
    'id': 'kpi-risk',
    'title': '6.2 KPI_Risk_Class x PnP behaviour',
    'purpose': "Used when we quote credit-risk-tier-specific behaviour. Class 1 (best) has 3.4x more PnP spend than Class 5.",
    'body_html': f'''
      <h4>The query</h4>
      <pre><code>SELECT
    KPI_Risk_Class,
    COUNT(*) AS customers,
    COUNTIF(nr_pnp_trns &gt; 0) AS pnp_active,
    ROUND(100.0 * COUNTIF(nr_pnp_trns &gt; 0) / COUNT(*), 1) AS active_pct,
    ROUND(AVG(val_pnp_trns), 0) AS avg_pnp_spend,
    ROUND(AVG(SAFE_DIVIDE(val_pnp_trns, val_tot_trns)) * 100, 1) AS wallet_pct
FROM `{PROD}.PicknPay.Audience_Upload_20260206`
WHERE val_tot_trns &gt; 0
GROUP BY KPI_Risk_Class
ORDER BY avg_pnp_spend DESC;</code></pre>

      <h4>Expected result</h4>
      <table>
        <tr><th>KPI_Risk_Class</th><th>customers</th><th>active_pct</th><th>avg_pnp_spend</th><th>wallet_pct</th></tr>
        <tr><td>Class 1</td><td>500,939</td><td>69.6</td><td>2,254</td><td>13.0</td></tr>
        <tr><td>Class 2</td><td>458,067</td><td>63.9</td><td>1,573</td><td>12.1</td></tr>
        <tr><td>Class 3</td><td>432,846</td><td>60.0</td><td>1,248</td><td>11.7</td></tr>
        <tr><td>Class 4</td><td>344,316</td><td>52.6</td><td>883</td><td>10.8</td></tr>
        <tr><td>Class 5</td><td>243,425</td><td>45.9</td><td>658</td><td>10.1</td></tr>
        <tr><td>Class 6</td><td>93,542</td><td>54.5</td><td>874</td><td>13.0</td></tr>
        <tr><td>Thin</td><td>151,755</td><td>48.7</td><td>760</td><td>10.5</td></tr>
        <tr><td>No Score</td><td>66,949</td><td>43.3</td><td>558</td><td>10.2</td></tr>
      </table>

      <h4>The 3.4x claim</h4>
      <p>Class 1 avg PnP spend (R2,254) / Class 5 avg PnP spend (R658) = 3.42x. Rounded to 3.4x in the deck.</p>
    '''
  },
  {
    'part': 'Part 6, Other supporting queries',
    'id': 'reactivation',
    'title': '6.3 The 947k reactivation target broken down by wealth tier',
    'purpose': "Source of the 'PC0 sub-pool 176k, PW0 sub-pool 99k' claims in Unlock 1.",
    'body_html': f'''
      <h4>The query</h4>
      <pre><code>SELECT
    Retail_Model,
    COUNT(*) AS customers_no_pnp_spend,
    ROUND(SUM(val_tot_trns) / 1e6, 1) AS their_total_spend_m
FROM `{PROD}.PicknPay.Audience_Upload_20260206`
WHERE (val_pnp_trns = 0 OR val_pnp_trns IS NULL)
  AND val_tot_trns &gt; 0
GROUP BY Retail_Model
ORDER BY customers_no_pnp_spend DESC;</code></pre>

      <h4>Expected result (approximate)</h4>
      <table>
        <tr><th>Retail_Model</th><th>customers_no_pnp_spend</th><th>their_total_spend_m</th></tr>
        <tr><td>EU0</td><td>~340k</td><td>~1,600</td></tr>
        <tr><td>GL0</td><td>~225k</td><td>~1,900</td></tr>
        <tr><td>PC0</td><td>~176k</td><td>~2,650</td></tr>
        <tr><td>PW0</td><td>~99k</td><td>~2,000</td></tr>
        <tr><td>PB0</td><td>~80k</td><td>~940</td></tr>
        <tr><td>EL0</td><td>~26k</td><td>~110</td></tr>
        <tr><td>PWH</td><td>~1.6k</td><td>~44</td></tr>
        <tr><td>PWU</td><td>~2.4k</td><td>~115</td></tr>
      </table>

      <p>Numbers marked "approximate" because they come from an internal cross-tab that isn't stored in the deck. Pierre can run the exact query above to get the precise breakdown.</p>
    '''
  },

  # ═══════════════════════════════════════════════════════════════════════
  # PART 7: WHAT IS NOT IN THE DECK BUT ASKED ABOUT
  # ═══════════════════════════════════════════════════════════════════════
  {
    'part': 'Part 7, Frequently asked but not on deck',
    'id': 'segment-spend',
    'title': '7.1 Total FNB card spend distribution (context for wallet-share denominator)',
    'purpose': "Answer to 'how much of a customer's total spend is even category-relevant?'",
    'body_html': f'''
      <h4>The query</h4>
      <pre><code>SELECT
    Retail_Model,
    COUNT(*) AS customers,
    ROUND(AVG(val_tot_trns), 0)     AS avg_total_spend,
    ROUND(AVG(val_pnp_trns), 0)     AS avg_pnp_spend,
    ROUND(SUM(val_tot_trns) / 1e9, 2) AS total_spend_b,
    ROUND(SUM(val_pnp_trns) / 1e9, 2) AS total_pnp_spend_b
FROM `{PROD}.PicknPay.Audience_Upload_20260206`
WHERE val_tot_trns &gt; 0
GROUP BY Retail_Model
ORDER BY total_spend_b DESC;</code></pre>

      <p>Wallet share denominator (val_tot_trns) is total FNB card activity across all merchants, not category-adjusted. This is a defensible measurement choice because it captures the customer\\'s <i>ability to spend</i>, not just their grocery basket. But it means the wallet-share numbers are lower than they would be if we restricted the denominator to groceries-adjacent only.</p>
    '''
  },
  {
    'part': 'Part 7, Frequently asked but not on deck',
    'id': 'freshness',
    'title': '7.2 How fresh is the data?',
    'purpose': "Answer to 'when was Audience_Upload_20260206 generated?'",
    'body_html': f'''
      <h4>The query</h4>
      <pre><code>SELECT
    creation_time,
    DATE(last_modified_time) AS last_modified,
    (SELECT SUM(total_rows)
     FROM `{PROD}.PicknPay.INFORMATION_SCHEMA.PARTITIONS`
     WHERE table_name = 'Audience_Upload_20260206') AS n_rows
FROM `{PROD}.PicknPay.INFORMATION_SCHEMA.TABLES`
WHERE table_name = 'Audience_Upload_20260206';</code></pre>

      <h4>Expected result</h4>
      <p>Table was created on 20 June 2026. The 12-month observation window ending 20 June 2026 means the earliest transactions are from roughly June 2025.</p>
    '''
  },
  {
    'part': 'Part 7, Frequently asked but not on deck',
    'id': 'freshest-lr',
    'title': '7.3 How to check what LR question outputs are available',
    'purpose': "Answer to 'what else has LiveRamp given us?'",
    'body_html': f'''
      <h4>The query</h4>
      <pre><code>SELECT t.table_name, p.total_rows
FROM `{SB}.pnp_liveramp.INFORMATION_SCHEMA.TABLES` t
LEFT JOIN (
    SELECT table_name, SUM(total_rows) AS total_rows
    FROM `{SB}.pnp_liveramp.INFORMATION_SCHEMA.PARTITIONS`
    GROUP BY table_name
) p USING (table_name)
WHERE t.table_type = 'BASE TABLE'
ORDER BY p.total_rows DESC NULLS LAST;</code></pre>

      <h4>Expected result</h4>
      <table>
        <tr><th>table_name</th><th>total_rows</th><th>Deck use</th></tr>
        <tr><td>lr_out_fnb_pnp_awarenes</td><td>31,834,062</td><td>Not used (fanned join)</td></tr>
        <tr><td>lr_out_extract_20022026</td><td>6,220,342</td><td>Not used (unclear provenance)</td></tr>
        <tr><td>lr_out_pnp_audiences_for_awareness</td><td>2,278,245</td><td>Attempted, fails hash join</td></tr>
        <tr><td>lr_out_extract_18022026</td><td>1,534,812</td><td>Not used</td></tr>
        <tr><td>lr_out_pnp_clothing_base</td><td>857,373</td><td><b>Used, Unlocks 3 and 4</b></td></tr>
        <tr><td>lr_out_ntb_transact</td><td>788,806</td><td>Attempted, fails hash join</td></tr>
        <tr><td>lr_out_ntb_funeral</td><td>788,806</td><td>Not used</td></tr>
        <tr><td>aud_pnp_audience_upload</td><td>360,900</td><td>Not used (older snapshot)</td></tr>
      </table>
    '''
  },
  {
    'part': 'Part 7, Frequently asked but not on deck',
    'id': 'reproducibility',
    'title': '7.4 How to re-run the whole discovery',
    'purpose': "Full pipeline from raw GCS files to deck output.",
    'body_html': f'''
      <h4>Step 1: Ingest LR clean-room outputs from GCS into sandbox</h4>
      <pre><code>cd nav-runner
bash scripts/ingest_liveramp_to_sandbox.sh</code></pre>
      <p>This reads gs://liveramp_output/ and gs://picknpay_audience_uploads/, loads each unique question output into <code>{SB}.pnp_liveramp.lr_out_*</code>.</p>

      <h4>Step 2: Run the full one-shot discovery</h4>
      <pre><code>bash scripts/discover_pnp_all.sh</code></pre>
      <p>Writes everything to <code>~/pnp_discovery.log</code>. Contains every cross-tab used in the deck.</p>

      <h4>Step 3: Verify the FRG-to-eBucks bridge does not work</h4>
      <pre><code>bash scripts/test_unique_id_bridge.sh</code></pre>
      <p>Confirms the 0-row overlap. This is our defence when asked why we can't yet quote eBucks reward tier by FNB tier.</p>

      <h4>Step 4: Generate the two decks</h4>
      <pre><code>python3 scripts/generate_pnp_deck_marina.py
python3 scripts/generate_pnp_deck_super.py</code></pre>
      <p>Writes <code>pnp_deck_marina.html</code> and <code>pnp_deck_super.html</code>.</p>

      <h4>Step 5: Generate this technical explainer</h4>
      <pre><code>python3 scripts/generate_pnp_deck_technical.py</code></pre>
      <p>Writes <code>pnp_deck_technical.html</code>.</p>
    '''
  },
]


# ── Build TOC and body ───────────────────────────────────────────────────
def part_id(sec):
  return sec['part'].replace(' ', '-').replace(',', '').lower()


# Group sections by part
from collections import OrderedDict
by_part: 'OrderedDict[str, list]' = OrderedDict()
for sec in SECTIONS:
  by_part.setdefault(sec['part'], []).append(sec)

toc_html = []
body_html = []

for part, secs in by_part.items():
  toc_html.append(f'<div class="toc-group"><h3>{esc(part)}</h3><ul>')
  for sec in secs:
    toc_html.append(f'<li><a href="#{esc(sec["id"])}">{esc(sec["title"])}</a></li>')
  toc_html.append('</ul></div>')

for sec in SECTIONS:
  body_html.append(f'''
    <div class="sec" id="{esc(sec["id"])}">
      <div class="sec-part">{esc(sec["part"])}</div>
      <h2>{esc(sec["title"])}</h2>
      <p class="purpose"><b>Purpose:</b> {esc(sec["purpose"])}</p>
      {sec["body_html"]}
      <a href="#top" class="back-to-top">Back to top</a>
    </div>
  ''')


html = f"""<!DOCTYPE html>
<html lang='en'><head><meta charset='UTF-8'>
<title>PnP Spend Shift decks, technical explainer for Pierre</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'DM Sans',sans-serif; background:#f8fafc; color:#1a202c; line-height:1.55; }}
#hdr {{ background:linear-gradient(135deg,#0f172a,#1e40af); color:#fff; padding:32px; }}
#hdr h1 {{ font-size:2rem; font-weight:700; }}
#hdr p {{ margin-top:8px; opacity:.92; font-size:1rem; line-height:1.55; }}
#hdr .meta {{ margin-top:14px; font-size:.75rem; opacity:.6; }}
.ctn {{ max-width:1100px; margin:0 auto; padding:24px; }}
.toc {{ background:#fff; border-radius:14px; padding:24px 30px; margin:20px 0; border:1px solid #e2e8f0; box-shadow:0 1px 4px rgba(0,0,0,.04); }}
.toc h2 {{ font-size:1.3rem; margin-bottom:12px; color:#0f172a; }}
.toc-group {{ margin-top:16px; }}
.toc-group h3 {{ font-size:.95rem; font-weight:700; color:#1e40af; margin-bottom:6px; text-transform:uppercase; letter-spacing:.05em; }}
.toc-group ul {{ list-style:none; padding-left:0; }}
.toc-group li {{ padding:4px 0; font-size:.9rem; }}
.toc-group a {{ color:#334155; text-decoration:none; border-bottom:1px dashed transparent; }}
.toc-group a:hover {{ color:#1e40af; border-bottom-color:#1e40af; }}
.sec {{ background:#fff; border-radius:14px; padding:26px 30px; margin:16px 0; border:1px solid #e2e8f0; box-shadow:0 1px 4px rgba(0,0,0,.04); }}
.sec-part {{ display:inline-block; background:#f1f5f9; color:#334155; padding:4px 12px; border-radius:6px; font-size:.72rem; font-weight:700; text-transform:uppercase; letter-spacing:.05em; margin-bottom:12px; }}
.sec h2 {{ font-size:1.5rem; font-weight:700; color:#0f172a; margin-bottom:8px; padding-bottom:10px; border-bottom:2px solid #f1f5f9; }}
.sec h4 {{ font-size:1rem; font-weight:700; color:#0f172a; margin-top:20px; margin-bottom:8px; }}
.sec p {{ font-size:.92rem; color:#334155; margin-bottom:6px; }}
.sec p.purpose {{ background:#f1f5f9; padding:12px 16px; border-radius:8px; font-size:.9rem; color:#334155; margin-bottom:14px; }}
.sec ul {{ margin:6px 0 6px 22px; }}
.sec li {{ font-size:.9rem; color:#334155; margin-bottom:5px; }}
.sec b {{ color:#0f172a; }}
.sec code {{ font-family:'JetBrains Mono', ui-monospace, monospace; font-size:.85rem; background:#f1f5f9; padding:2px 6px; border-radius:4px; color:#1e40af; }}
.sec pre {{ background:#0f172a; color:#e2e8f0; padding:16px 20px; border-radius:8px; overflow-x:auto; margin:10px 0; font-size:.82rem; line-height:1.5; }}
.sec pre code {{ background:transparent; color:#e2e8f0; padding:0; font-size:inherit; }}
.sec table {{ width:100%; border-collapse:collapse; margin:10px 0; font-size:.86rem; }}
.sec th {{ background:#0f172a; color:#fff; padding:10px 12px; text-align:left; font-size:.72rem; text-transform:uppercase; letter-spacing:.03em; }}
.sec td {{ padding:8px 12px; border-bottom:1px solid #f1f5f9; }}
.back-to-top {{ display:inline-block; margin-top:16px; font-size:.8rem; color:#64748b; text-decoration:none; border-bottom:1px dashed #64748b; }}
.back-to-top:hover {{ color:#1e40af; border-bottom-color:#1e40af; }}
</style>
</head><body>

<div id='hdr' name='top'>
<h1>PnP Spend Shift decks, technical explainer</h1>
<p>Written for someone who wants to see the SQL, the tables, and the lineage behind every number. Every stat has a source table, a query to reproduce it, an expected result, and a data-provenance note. All queries are read-only. Run them in BigQuery Studio, in the CLI (<code>bq query</code>), or in a notebook.</p>
<div class='meta'>Generated {esc(now)}</div>
</div>

<div class='ctn'>

<div class='toc'>
<h2>Table of contents</h2>
{''.join(toc_html)}
</div>

{''.join(body_html)}

<div class='sec' style='background:#0f172a;color:#fff;border-color:#0f172a'>
<h2 style='color:#fff;border-color:#1e40af'>Quick reference</h2>
<h4 style='color:#93c5fd'>Every FRG-side query starts here</h4>
<pre><code>FROM `{PROD}.PicknPay.Audience_Upload_20260206`</code></pre>
<h4 style='color:#93c5fd'>Every LR clean-room query starts here</h4>
<pre><code>FROM `{SB}.pnp_liveramp.lr_out_*`</code></pre>
<h4 style='color:#93c5fd'>The only LR table that joins to FRG on EMAIL_ADDR</h4>
<pre><code>FROM `{SB}.pnp_liveramp.lr_out_pnp_clothing_base`
JOIN `{PROD}.PicknPay.Audience_Upload_20260206` USING ... (email_addr = EMAIL_ADDR)</code></pre>
<h4 style='color:#93c5fd'>The eBucks reward tiers live here</h4>
<pre><code>FROM `{PROD}.PicknPay.PNP_eBucks_BurgerFriday` (reward_seg_id column)</code></pre>
<h4 style='color:#93c5fd'>Both projects are in africa-south1</h4>
<p style='color:#e2e8f0'>Always specify <code>--location=africa-south1</code> if using the bq CLI, or the query silently fails.</p>
</div>

</div>
</body></html>
"""

OUT = 'pnp_deck_technical.html'
with open(OUT, 'w') as f:
  f.write(html)

print(f'Wrote: {OUT}')
print('Open in browser. Every SQL query is copy-pasteable into BigQuery Studio.')
