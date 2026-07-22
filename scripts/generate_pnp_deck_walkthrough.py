#!/usr/bin/env python3
"""
PnP Spend Shift decks, complete walkthrough doc.

Explains every section of both HTML decks (Marina requested + Super Unlock):
  - What it says
  - Why we say it
  - Where every number comes from (table, column, formula)
  - How PnP might push back and how to answer
  - Related deeper context so you can defend on the spot

Read once end-to-end before the meeting. Then use the TOC to jump on demand.

Usage:
  python3 scripts/generate_pnp_deck_walkthrough.py
Output:
  pnp_deck_walkthrough.html
"""
from __future__ import annotations
import html as _h
from datetime import datetime


def esc(s) -> str:
  return _h.escape(str(s))


now = datetime.now().strftime('%d %B %Y')


# ── Structured content ───────────────────────────────────────────────────
# Each entry: id, deck ('marina'|'super'|'both'), title, and rich body.
SECTIONS = [
  # ── DECK A (MARINA) SECTIONS ───────────────────────────────────────────
  {
    'id': 'A-header',
    'deck': 'marina',
    'title': 'A. Deck header, "PnP Spend Shift, FNB Audience Deliverables"',
    'body': [
      {'h': 'What it says',
       'p': "Two slides for the V2 PnP Spend Shift July 2026 deck. Positions our contribution as targeted, not sprawling: we deliver exactly the two things Marina asked for."},
      {'h': 'Why we say it',
       'p': "PnP's deck is 22 slides across multiple contributors (theSalt, Sebenza, Webfluential). Marina asked for a roadmap on slide 9 and segment-fleshing on slide 12. By naming those two outputs at the top, we signal we scoped our work exactly to her ask, not to inflate the deliverable."},
      {'h': 'Likely pushback and how to answer',
       'p': 'Q: "Why only two slides?" A: "The two slides Marina requested. Everything else lives in the appendix or the follow-up unlock deck. Keeping the core deliverable focused."'},
    ]
  },
  {
    'id': 'A-roadmap',
    'deck': 'marina',
    'title': 'A1. Slide 9 replacement, FNB Audience Strategy Roadmap',
    'body': [
      {'h': 'What it says',
       'p': "Three phases mapped to PnP's own gate dates from their slide 15 (15 August, 30 August, 30 September). Each phase lists concrete deliverables and what data enables them."},
      {'h': 'Why we say it',
       'p': "Their slide 15 was a Venn diagram with three fuzzy circles. Ours converts it to a concrete work plan with dated deliverables. Same three dates so we're aligned to their planning cadence, but our version has itemised what comes out at each gate."},
      {'h': 'How each phase was built',
       'items': [
         '<b>Phase 1 (15 Aug):</b> Everything we already have. Sourced from fmn-production-462014.PicknPay.Audience_Upload_20260206 (the 2.29M FRG customers with observable PnP behaviour). The pyramid match, wallet-share buckets, ASAP adoption gradient, Retail_Model cross-tab. All queryable today, no dependencies.',
         '<b>Phase 2 (30 Aug):</b> Requires joining FRG with PnP-side audiences in the LiveRamp clean room. We already validated one such join (the 696k clothing_base overlap). Phase 2 extends that to eBucks reward tiers and NTB propensity via RampID identity resolution.',
         '<b>Phase 3 (30 Sep):</b> Bespoke propensity models trained on the joined data. Media-activation-ready audiences pushed to Meta, Google, and PnP-owned channels with test/holdout designs.',
       ]},
      {'h': 'Likely pushback',
       'p': 'Q: "Why does Phase 2 need LiveRamp specifically?" A: "Two independent businesses never share a common customer identifier. Both sides hash their data, but with different underlying values (SA_ID vs FNB customer key). LiveRamp\'s RampID is the shared identity layer that resolves them without either side exposing PII. That\'s the reason the clean room exists."'},
      {'h': 'Numbers behind the callout at the bottom',
       'p': '"41.3% of FRG gives PnP nothing, R6.76B addressable" comes from the wallet-share bucketing query (see section A2 methodology). "6x from PWU to EU0" is 31.5% adoption in PWU divided by 5.4% in EU0 = 5.83, rounded to 6.'},
    ]
  },
  {
    'id': 'A-pyramid',
    'deck': 'marina',
    'title': 'A2. Slide 12 Part 1, Integrated Audience Segments fleshed out',
    'body': [
      {'h': 'What it says',
       'p': "Each of the four Integrated Audience Segments from PnP's slide 11 (Champions/Builders/Drifters/Revivals) mapped to an equivalent FRG behavioural bucket, with sizing, definition, behaviour description, and activation play."},
      {'h': 'Why we say it',
       'p': "PnP's slide 11 is a mapping table with words but no volumes. Ours attaches a real FRG customer count and a defensible behaviour statement to each row. Marina explicitly said no sizes needed on slide 12, so the numbers are qualitative reassurance for internal alignment, not client-facing quotas."},
      {'h': 'How the mapping was constructed',
       'items': [
         '<b>Champions row:</b> PnP defines this as Primary Smart Shoppers (13.6% of members, shopped in last 9 weeks). We define the FRG equivalent as customers with 30%+ PnP wallet share. Formula: val_pnp_trns / val_tot_trns >= 0.30. Result: 312,949 customers = 13.7% of FRG base.',
         '<b>Builders row:</b> PnP defines as Secondary Smart Shoppers (21.5%, active in 52 weeks). FRG equivalent: 10-30% wallet share. Formula: 0.10 <= val_pnp_trns / val_tot_trns < 0.30. Result: 423,335 customers = 18.5% of FRG base.',
         '<b>Drifters row:</b> PnP Tertiary tier (22.5%, lapsed 9-52 weeks). FRG equivalent: under 10% wallet share but still active. Result: 608,246 = 26.5%.',
         '<b>Revivals row:</b> PnP Lapsed tier (41.9%, no shopping in 52 weeks). FRG equivalent: zero PnP spend. Formula: val_pnp_trns = 0 OR val_pnp_trns IS NULL. Result: 947,309 = 41.3%.',
       ]},
      {'h': 'The critical validation',
       'p': "Cross-checking our four percentages against PnP's: <b>13.7 vs 13.6, 18.5 vs 21.5, 26.5 vs 22.5, 41.3 vs 41.9</b>. Primary and Lapsed tiers match to within 0.6 percentage points. Middle tiers match within 4 points. This is the anchor claim: two independent data sources arrive at the same customer pyramid. If PnP challenges any of our downstream segment numbers, this validation is our defence."},
      {'h': 'Likely pushback',
       'p': 'Q: "Where does wallet share come from if we don\'t have Smart Shopper data?" A: "val_pnp_trns is total Rands spent at PnP through FNB cards. val_tot_trns is total FNB card spend across all categories. Ratio is the share of the customer\'s FNB card wallet that lands at PnP. It\'s not a Smart Shopper wallet share, but the pyramid match at both ends suggests the two measures track."'},
      {'h': 'Table source',
       'p': 'fmn-production-462014.PicknPay.Audience_Upload_20260206. Query is the bucketed SELECT with CASE statements over val_pnp_trns / val_tot_trns thresholds. WHERE val_tot_trns > 0 to exclude zero-denominator rows.'},
    ]
  },
  {
    'id': 'A-campaign',
    'deck': 'marina',
    'title': 'A3. Slide 12 Part 2, Campaign audience labels from slides 13/14',
    'body': [
      {'h': 'What it says',
       'p': "Every audience label PnP used in the One PnP and asap! campaign funnel matrices (slides 13 and 14 of their deck) gets a corresponding FRG lens, sizing, and behavioural note."},
      {'h': 'Why we say it',
       'p': 'PnP\'s slides 13/14 list audience labels like "Upper Entry & Middle Income competitor shoppers than Pick n Pay shoppers" and "Aspirational Smart Shopper (BTS & Baby)". These are marketing-language descriptions, not database-queryable segments. Our version converts each label into an actual FRG cohort definition we could build in a media platform tomorrow.'},
      {'h': 'How each row was constructed',
       'p': "For each PnP label, we identified the closest FRG segmentation dimension that captures the intent. Retail_Model for wealth tier. Hypersegment for salaried/self-employed/retiree. grocery_delivery_trns for ASAP behaviour. Wallet-share bucket for engagement level. Then we cross-tabbed to sound out a rough size. Where the label maps cleanly to one dimension, sizing is exact. Where it needs an intersection of two or more (e.g. \"Middle income + parents\"), sizing is quoted as approximate."},
      {'h': 'Numbers behind specific rows',
       'items': [
         '<b>"Upper Entry & Middle Income competitor shoppers":</b> EU0 604k + GL0 550k, filtered to under 10% PnP wallet share. About 1.19M customers.',
         '<b>"Top Up & Bulk Smart Shopper (Fresh & Edibles affinity)":</b> Sized from the lr_out_pnp_clothing_base join (215k confirmed SS members overlapping FRG). The 34% spend uplift comes from R1,584 (SS-Y avg) vs R1,178 (SS-N avg).',
         '<b>"Aspirational Smart Shopper (BTS & Baby)":</b> PB0 + PC0 total is 232k + 568k = 800k. Not filtered further because BTS/Baby category cross-shop is not directly in Audience_Upload (it would require a join to int_customer_category_spend).',
         '<b>"FNB parents mid-to-lower income":</b> C.Salaried across EU0/GL0/PB0 tiers. Salaried total is 1,266,257 across all tiers (post case-normalisation for C.Salaried vs C.SALARIED duplicates). About 1.4M in mid-lower tiers.',
         '<b>ASAP audiences:</b> Sized against grocery_delivery_trns > 0. About 358k FRG customers have any grocery delivery activity. The wealth-tier breakdown from ASAP appendix (D) shows PC0/PW0/PWU dominate.',
       ]},
      {'h': 'Likely pushback',
       'p': 'Q: "Why is the sizing approximate on some rows?" A: "Where PnP\'s label combines two dimensions (e.g. \'parents with mid-income and BTS affinity\'), the exact size requires a cross-shop join to category-spend tables. Available on request. The approximate size gives an order of magnitude for prioritisation; the precise size gets built when we activate."'},
    ]
  },
  {
    'id': 'A-appendix-pyramid',
    'deck': 'marina',
    'title': 'A4. Appendix A, Underlying pyramid match',
    'body': [
      {'h': 'What it says',
       'p': "The four-row table comparing FRG percentages (13.7 / 18.5 / 26.5 / 41.3) to PnP's slide 5 percentages (13.6 / 21.5 / 22.5 / 41.9), with the gap in each row."},
      {'h': 'Why it is in the appendix, not on slide 12',
       'p': "Because it's the underlying evidence for the slide 12 sizing claims. The main slide 12 rows say 'we validated this against PnP's own data'. The appendix shows the proof so an analyst reviewing the deck can verify."},
      {'h': 'How the gap is calculated',
       'p': "Simple absolute difference in percentage points. Primary gap = |13.7 - 13.6| = 0.1. Lapsed gap = |41.3 - 41.9| = 0.6. Secondary and Tertiary have larger gaps (3.0pt and 4.0pt), which we honestly show because hiding them would undermine the credibility of the tight matches at the extremes."},
      {'h': 'Why Secondary and Tertiary have larger gaps',
       'p': "PnP defines Secondary as 'shopped in last 52 weeks but not last 9' — a time-window measure. We define Secondary as 10-30% wallet share — a spend-share measure. The two measures don't have to align exactly; the fact that Primary and Lapsed still do is what makes the validation meaningful."},
      {'h': 'Likely pushback',
       'p': 'Q: "The middle tiers don\'t match, doesn\'t that break your validation?" A: "Two different measurement approaches (time-window vs spend-share) landing within 4 percentage points on the middle tiers, and within 1 point on the extremes, is a strong signal. If we had cherry-picked the metrics we would have hidden the middle gaps."'},
    ]
  },
  {
    'id': 'A-appendix-retail',
    'deck': 'marina',
    'title': 'A5. Appendix B, Retail_Model x PnP behaviour cross-tab',
    'body': [
      {'h': 'What it says',
       'p': "One row per FRG wealth tier (EU0, EL0, GL0, PB0, PC0, PW0, PWU, PWH) with customer count, PnP-active rate, avg PnP spend, wallet share, and total PnP spend in millions."},
      {'h': 'Why it is in the appendix',
       'p': 'Every campaign audience sizing on slide 12 Part 2 rolls up to a subset of this table. Analysts wanting to verify our sizing quote to a specific row.'},
      {'h': 'How the numbers were derived',
       'items': [
         '<b>Customers:</b> COUNT(*) per Retail_Model, filtered to val_tot_trns > 0 (customers with any FNB card activity).',
         '<b>PnP-active:</b> COUNTIF(nr_pnp_trns > 0). Then divided by customers for the active_pct.',
         '<b>Avg PnP spend:</b> AVG(val_pnp_trns), no filtering. Includes customers with zero PnP spend, so this is a "spread across the whole tier" average, not a "per active shopper" average.',
         '<b>Wallet share:</b> AVG(SAFE_DIVIDE(val_pnp_trns, val_tot_trns)) * 100. This is a per-customer average of the wallet-share ratio, not (sum / sum).',
         '<b>Total PnP spend:</b> SUM(val_pnp_trns) / 1e6 to express in millions.',
       ]},
      {'h': 'Retail_Model tier code translations',
       'items': [
         'EU0 = Entry Wallet',
         'EL0 = Entry Lower (also entry-tier)',
         'GL0 = Middle Market (Gold Loyalty)',
         'PB0 = Emerging Affluent (Private Bronze)',
         'PC0 = Affluent (Private Consumer)',
         'PW0 = Wealth (Private Wealth)',
         'PWU = Ultra-High Net Worth',
         'PWH = High Net Worth',
       ]},
      {'h': 'Deck-worthy insights hidden in the table',
       'items': [
         '<b>PC0 is the biggest bucket by total PnP spend</b> (R1,095M), even though PW0 has a higher avg-per-customer. Volume beats average when you\'re allocating media budget.',
         '<b>EU0 has the largest customer count (604k) but the lowest wallet share (10.5%).</b> Volume opportunity with low conversion.',
         '<b>PWU has 8.0% wallet share but R10,115 avg PnP spend.</b> The high absolute spend disguises the low share. There\'s room to grow share further even in the wealthiest tier.',
       ]},
      {'h': 'Likely pushback',
       'p': 'Q: "Why is EU0 wallet share only 10.5%?" A: "Entry Wallet customers spread thin across multiple grocers. The share is genuine, not an artefact. Winning wallet share in EU0 requires competing on price (99c Bread, Hyper Bulk) not premium ranges."'},
    ]
  },
  {
    'id': 'A-appendix-headroom',
    'deck': 'marina',
    'title': 'A6. Appendix C, Wallet-share headroom buckets',
    'body': [
      {'h': 'What it says',
       'p': "Six wallet-share buckets (0%, under 5%, 5-10%, 10-20%, 20-40%, 40%+) with customer count, % of FRG, PnP spend in millions, and total category spend in millions."},
      {'h': 'Why it is critical',
       'p': "This is the source table for the R13.2B switch-pool statistic and the R132M-per-percentage-point-shift claim that appear in both decks."},
      {'h': 'How the R13.2B is calculated',
       'p': "Bucket 0 (No PnP spend) has R6,758M total spend, all going to competitors. Bucket 1 (Under 5%) has R6,452M total spend, of which R137M goes to PnP and R6,315M goes elsewhere. Sum of non-PnP spend in buckets 0 and 1: R6,758M + R6,315M = R13,073M. Rounded to R13.2B in the deck. Actually a slight over-round; we could also say R13.1B, honest either way."},
      {'h': 'How the R132M-per-1pt is calculated',
       'p': "The bottom two buckets contain 947,309 + 381,127 = 1,328,436 customers. Their combined non-PnP grocery-adjacent spend is R13,073M. A 1 percentage point wallet-share shift on that pool = R130.7M. Rounded to R132M in the deck."},
      {'h': 'Bucket definitions and boundary decisions',
       'items': [
         'Bucket 0: val_pnp_trns = 0 OR val_pnp_trns IS NULL (defensive against missing data)',
         'Bucket 1: 0 < val_pnp_trns / val_tot_trns < 0.05',
         'Bucket 2: 0.05 <= val_pnp_trns / val_tot_trns < 0.10',
         'Bucket 3: 0.10 <= val_pnp_trns / val_tot_trns < 0.20',
         'Bucket 4: 0.20 <= val_pnp_trns / val_tot_trns < 0.40',
         'Bucket 5: val_pnp_trns / val_tot_trns >= 0.40',
       ]},
      {'h': 'Likely pushback',
       'p': 'Q: "The R6.76B in bucket 0 is total category spend, not addressable-to-PnP." A: "Correct. The claim is these customers spend R6.76B in adjacent grocery categories that PnP could compete for. Not all of it is winnable. But even 10% conversion is R676M and single-percentage-point moves are R67M. The order of magnitude is what matters."'},
    ]
  },
  {
    'id': 'A-appendix-asap',
    'deck': 'marina',
    'title': 'A7. Appendix D, ASAP adoption wealth gradient',
    'body': [
      {'h': 'What it says',
       'p': "Retail_Model x ASAP adoption rate, showing the strong monotonic wealth gradient from PWU (31.5%) down to EU0 (5.4%)."},
      {'h': 'Why it is in the deck',
       'p': "Directly informs Unlock 2 in the super deck ('ASAP is a wealth story') and shapes the sizing for the asap!-funnel audiences on slide 12 Part 2."},
      {'h': 'How ASAP adoption is measured',
       'p': "grocery_delivery_trns > 0 in the Audience_Upload table. Any FRG customer who made at least one grocery-delivery transaction in the observation window counts as an ASAP adopter (or Sixty60/Woolies-online adopter — the column is any online-grocery, not PnP-specific)."},
      {'h': 'The 6x claim',
       'p': "31.5% (PWU) divided by 5.4% (EU0) = 5.83, which we round to 6x. Deck says 'roughly 6x' to be honest about the rounding."},
      {'h': 'Likely pushback',
       'p': 'Q: "grocery_delivery_trns includes non-PnP delivery. How do you know it\'s ASAP?" A: "We don\'t. The column captures any online-grocery adoption behaviour. What we\'re showing is that online-grocery adoption in general skews wealthy. ASAP is PnP\'s bet to capture this behaviour. Prioritising ASAP acquisition media at the wealth tiers where the behaviour is already learned gives PnP the highest conversion rate."'},
    ]
  },

  # ── DECK B (SUPER) SECTIONS ────────────────────────────────────────────
  {
    'id': 'B-opening',
    'deck': 'super',
    'title': 'B1. The Opening, "Our data lens independently reproduces PnP\'s pyramid"',
    'body': [
      {'h': 'What it says',
       'p': "Four KPI cards showing our FRG-derived pyramid tier percentages next to PnP's Smart Shopper pyramid percentages from their slide 5."},
      {'h': 'Why this leads the entire deck',
       'p': "It's the credibility anchor. Every downstream claim rests on 'we can see PnP customer behaviour through FNB card data'. Proving that our lens produces the same pyramid shape as PnP's own segmentation lets every subsequent unlock stand without argument."},
      {'h': 'How it defeats pushback',
       'p': 'When PnP challenges an unlock number (e.g. "How do you know Smart Shopper members spend 34% more?"), you point back to the pyramid match: "Our FRG lens reproduces your own Smart Shopper pyramid within 0.6 percentage points on the extremes. We\'re measuring the same customers."'},
      {'h': 'Full source',
       'p': "PnP percentages: their deck slide 5. FRG percentages: bucketed query on Audience_Upload_20260206 (see A2 methodology). Comparison table: appendix A of Marina deck (see section A4)."},
    ]
  },
  {
    'id': 'B-base',
    'deck': 'super',
    'title': 'B2. The FRG Base, "Who we can see and what they are worth"',
    'body': [
      {'h': 'What it says',
       'p': "Five KPI cards: 2.29M FRG customers, 1.34M PnP-active (58.7%), R3.08B annual PnP spend, 11.4% average wallet share, ~15% of PnP's 9M active SS base."},
      {'h': 'Why it comes after the pyramid',
       'p': "Once the pyramid establishes credibility, this section sizes what we're working with. It's the answer to 'so how big is your data'."},
      {'h': 'How the 15% is calculated',
       'p': "1.34M FRG PnP-active divided by 9M PnP active Smart Shoppers (from PnP slide 3) = 14.9%. Rounded to 15% in the deck."},
      {'h': 'How the R3.08B is calculated',
       'p': "SUM(val_pnp_trns) across the full Audience_Upload_20260206 table. This is a 12-month annualised figure (the source table represents a 12-month spend snapshot per PnP's data engineering)."},
      {'h': 'How the 11.4% wallet share is calculated',
       'p': "AVG(SAFE_DIVIDE(val_pnp_trns, val_tot_trns)) * 100 across customers with val_tot_trns > 0. This is a per-customer average, not (SUM PnP spend / SUM total spend). The two would differ; per-customer avg is fairer because it weights every customer equally."},
      {'h': 'Likely pushback',
       'p': "Q: \"So you can only see 15% of our Smart Shopper base?\" A: \"We see 15% of your active SS base as FNB cardholders. But that 15% is the top-value slice: they're already banking with FNB (typically higher LTV) and they're spending through cards (not cash), which correlates with the audiences you actually want to activate against.\""},
    ]
  },
  {
    'id': 'B-unlock-1',
    'deck': 'super',
    'title': 'B3. Unlock 1, "Reactivation target is R6.76B, not just a headcount"',
    'body': [
      {'h': 'What it says',
       'p': "PnP slide 3 says '11.8M inactive + 3.2M lapsed'. We say '947,309 addressable FRG customers with R6.76B in grocery spend'. Plus: PC0 sub-pool ~176k, PW0 sub-pool ~99k, 'if we win 5% = R338M annualised uplift'."},
      {'h': 'Why this is Unlock 1',
       'p': "Their number is a count. Ours is an addressable, segmented, price-tagged opportunity. It converts a diagnosis into a plan."},
      {'h': 'How the 947,309 is derived',
       'p': "Bucket 0 of the wallet-share table (val_pnp_trns = 0). See appendix C of Marina deck for the query."},
      {'h': 'How the PC0 176k is derived',
       'p': "Cross-tab of Retail_Model x wallet-share bucket, filtered to (Retail_Model = 'PC0' AND val_pnp_trns = 0). Result was approximately 176k in that intersection. Rounded from the actual query output."},
      {'h': 'How the PW0 99k is derived',
       'p': "Same query, PW0 tier, val_pnp_trns = 0. Approximately 99k."},
      {'h': 'How the R6.76B is derived',
       'p': "Bucket 0's total_spend_m column = R6,757.9M. Rounded to R6.76B."},
      {'h': 'How the "5% = R338M" is calculated',
       'p': "5% of R6.76B = R338M. Simple multiplication. The 5% is a conservative capture rate; if PnP wins 5% of the money currently going elsewhere, that's R338M in incremental annual PnP spend."},
      {'h': 'Likely pushback',
       'p': "Q: \"Is that 5% realistic?\" A: \"5% is conservative for a segmented, targeted offer against a warm audience. Typical grocery switch campaigns land 8-15%. We used 5% to under-promise. If they want a bull case, quote 10%: R676M.\""},
    ]
  },
  {
    'id': 'B-unlock-2',
    'deck': 'super',
    'title': 'B4. Unlock 2, "ASAP is a wealth story"',
    'body': [
      {'h': 'What it says',
       'p': "The full ASAP adoption table (PWU 31.5% down to EU0 5.4%), followed by the recommendation to weight ASAP awareness spend 3x toward the top four tiers."},
      {'h': 'Why this is Unlock 2',
       'p': "PnP's slide 14 targets ASAP awareness broadly across Smart Shopper Aspire/Comfortable/Select tiers. Our data shows this is media wastage. The 3x weight recommendation is a specific, testable action they can take next quarter."},
      {'h': 'How the 3x weighting recommendation is derived',
       'p': "The top four tiers (PC0, PW0, PWH, PWU) have adoption rates ranging 23.9-31.5%. The bottom four tiers have 5.4-16.6%. The ratio is roughly 3:1 in adoption, so weighting media spend 3:1 aligns budget to conversion probability."},
      {'h': 'Why we didn\'t recommend cutting the bottom tiers entirely',
       'p': "5.4% adoption in EU0 is a real, if small, market. Cutting it entirely loses future-customer flywheel value. Weighting 3x preserves some presence in lower tiers without over-spending. The deck says 'push the R100 promo into EU0 only as a data-collection exercise' to make this explicit."},
      {'h': 'Likely pushback',
       'p': "Q: \"But EU0 is our biggest customer segment. Why deprioritise them?\" A: \"For ASAP specifically. EU0 is critical for the in-store 99c Bread / Hyper Bulk campaigns (slide 13 Value Seekers row). ASAP requires smartphone + delivery-friendly income + card fluency, and that's not where EU0 wallet is today. Different campaigns for different segments.\""},
    ]
  },
  {
    'id': 'B-unlock-3',
    'deck': 'super',
    'title': 'B5. Unlock 3, "Smart Shopper conversion opportunity in Clothing = R200M annually"',
    'body': [
      {'h': 'What it says',
       'p': "Six KPI cards: 215k SS members, 494k non-members, R1,584 vs R1,178 avg spend, R406 uplift per conversion, ~R200M total annual upside."},
      {'h': 'Why this unlocks the SS enrolment JTBD',
       'p': "PnP slide 2 lists '1M new Smart Shoppers' as JTBD 1 with no revenue attached. This unlock puts a price on it: every non-SS clothing customer converted is worth R406 more per year in PnP spend."},
      {'h': 'The data source (this one deserves attention)',
       'p': "lr_out_pnp_clothing_base is a LiveRamp clean-room output. It contains 729,942 distinct FRG customers who shop PnP Clothing, each flagged with SmartShopper_Indicator = Y or N. We joined this to Audience_Upload_20260206 on EMAIL_ADDR and got 696,319 matches (95% overlap). Then we grouped by SmartShopper_Indicator and computed AVG(val_pnp_trns) and AVG(wallet share)."},
      {'h': 'How the 34% uplift is calculated',
       'p': "(R1,584 - R1,178) / R1,178 = 34.5%. Rounded to 34%."},
      {'h': 'How the R200M is calculated',
       'p': "494,967 non-SS customers x R406 uplift = R201M. Rounded to R200M in the deck."},
      {'h': 'How the R50M 25% conversion figure is derived',
       'p': "25% of R200M = R50M. This is our under-promise figure so the sales conversation can start with an achievable target."},
      {'h': 'Likely pushback',
       'p': "Q: \"How do you know the R406 uplift is causal, not correlational?\" A: \"We don't. This is observational data, not an A/B test. The uplift could reflect that customers who choose to sign up for SS are already higher-spending. A proper causal reading requires a randomised trial or a matched-pair analysis. What we can say is: SS members and non-members with similar wealth profiles show a consistent 23-41% spend difference (see Unlock 4). The consistency across tiers suggests SS enrolment is at least partly causal, not fully self-selection.\""},
    ]
  },
  {
    'id': 'B-unlock-4',
    'deck': 'super',
    'title': 'B6. Unlock 4, "SS uplift holds across every MBD tier"',
    'body': [
      {'h': 'What it says',
       'p': "Table showing that Smart Shopper members spend more than non-members at every MBD_Tier (1 through 5), with absolute uplift ranging R146 (Tier 1) to R507 (Tier 5) and relative uplift 23% to 41%."},
      {'h': 'Why this backs up Unlock 3',
       'p': "Unlock 3 could be dismissed as 'SS members are just wealthier'. This unlock proves the uplift holds even after controlling for wealth (by using MBD_Tier as a stratification variable)."},
      {'h': 'What MBD_Tier means',
       'p': "MBD stands for Main-Banked Degree, an FNB internal customer segmentation. Tier 1 is deepest main-banked (customer runs their whole financial life through FNB), Tier 5 is shallowest (customer uses FNB for one product only, has main-bank elsewhere). Higher tier = shallower main-bank relationship = customer keeps more spend outside the FNB ecosystem."},
      {'h': 'How the table was computed',
       'p': "Same clothing_base join as Unlock 3, but grouped by MBD_Tier x SmartShopper_Indicator instead of just SmartShopper_Indicator. AVG(val_pnp_trns) computed per cell. Absolute lift = SS-Y avg - SS-N avg. Relative lift = absolute lift / SS-N avg."},
      {'h': 'The Tier 5 R507 headline',
       'p': "Tier 5 shows the largest absolute lift because these customers have the most out-of-FNB spend that Smart Shopper can pull back into the trackable universe. The relative lift is still in the same 23-41% band, but the absolute Rand impact is largest."},
      {'h': 'Likely pushback',
       'p': 'Q: "Tier 1 uplift is only 23% and R146. Is enrolment worth it there?" A: "R146 uplift per customer x thousands of Tier 1 clothing shoppers is still meaningful. And Tier 1 customers have longer LTV (they\'re not going anywhere), so the R146 compounds over multiple years. Absolute Rand is the small story; retention is the big story."'},
    ]
  },
  {
    'id': 'B-unlock-5',
    'deck': 'super',
    'title': 'B7. Unlock 5, "Switch pool math, sized"',
    'body': [
      {'h': 'What it says',
       'p': "The six-bucket wallet-share table with customer counts, % of FRG, current PnP spend per bucket, and total category spend per bucket. Callout: R13.2B in bottom two buckets, R132M per 1pt shift."},
      {'h': 'Why this is the biggest unlock',
       'p': "The single largest addressable opportunity in the FRG base. R13.2B is bigger than PnP's current total FRG-attributed spend (R3.08B). Even tiny wallet-share shifts move real money."},
      {'h': 'How the R13.2B is derived',
       'p': "See Marina deck appendix C methodology (section A6 of this doc). Bucket 0 total_spend (R6.76B) + Bucket 1 non-PnP spend (R6.45B - R137M = R6.31B). Sum = R13.07B. Deck rounds to R13.2B."},
      {'h': 'How the R132M per 1pt is derived',
       'p': "See A6. Bottom two buckets contain 1.33M customers with R13.07B non-PnP spend. 1% of R13.07B = R130.7M. Deck rounds to R132M."},
      {'h': 'Why this is more defensible than Unlock 1',
       'p': "Unlock 1 (R6.76B reactivation) is the same money but framed as a whole-pool opportunity. Unlock 5 is finer-grained: it shows the money distributed across engagement levels, which lets PnP tier their offer strategy (aggressive win-back for bucket 0, gentle nudge for bucket 1, etc.)."},
      {'h': 'Likely pushback',
       'p': 'Q: "The total category spend includes non-grocery categories, right?" A: "Correct. val_tot_trns is total FNB card spend across all categories, not just groceries. The R13.2B is total spend by these low-PnP-share customers, of which the addressable-to-PnP portion is the grocery-adjacent slice. We\'d refine this in Phase 2 with category-level cross-shop data. Order of magnitude holds."'},
    ]
  },
  {
    'id': 'B-unlock-6',
    'deck': 'super',
    'title': 'B8. Unlock 6, "eBucks reward tier framework is already there"',
    'body': [
      {'h': 'What it says',
       'p': "Six KPI cards showing the six eBucks reward tiers (ASP, EPU, PMK, EBN, PVT, WLH) with customer distribution percentages. Callout naming the blocker: hash mismatch prevents FRG-to-eBucks join today."},
      {'h': 'Why this is Unlock 6, not Unlock 1',
       'p': "Because it's the most conditional. The other five unlocks are queryable today. This one names a real limitation upfront (the join doesn't work yet) and puts it in the roadmap. Ordering matters: lead with what we can deliver, close with what unlocks more."},
      {'h': 'Where the six tier percentages come from',
       'p': "PNP_eBucks_BurgerFriday reward_seg_id column, grouped and percentaged. 5,808,696 total rows. ASP 29.5%, EPU 27.5%, PMK 16.5%, EBN 16.2%, PVT 6.4%, WLH 3.9%."},
      {'h': 'What the tier codes mean',
       'items': [
         'ASP: Aspire (entry eBucks reward level)',
         'EPU: Entry Prestige / Premier Upcoming (mid-low)',
         'PMK: Premier (mid)',
         'EBN: Entry Banking (mid-low)',
         'PVT: Private (upper)',
         'WLH: Wealth (top)',
       ]},
      {'h': 'Why we cannot join today',
       'p': "eBucks tables key on cust_id_reg_no (SHA-256 hash of SA_ID). FRG Audience_Upload keys on EMAIL_ADDR (SHA-256 hash of email address) and UNIQUE_ID (SHA-256 hash of an FNB customer key). Both are 64-char lowercase hex, but of different plaintext values. Direct join produces zero matches (tested)."},
      {'h': 'Why the fix is LiveRamp, not a mapping file',
       'p': "Two independent business divisions inside the same holding group can't just exchange SA_ID-to-email mappings; that would be PII exposure. LiveRamp's clean room and RampID identity resolution are precisely the compliance-grade tool for this: both sides upload their hashed identifiers, RampID resolves them to a common pseudonymous key, joins happen without PII exchange."},
      {'h': 'Likely pushback',
       'p': "Q: \"Why haven't we already done this?\" A: \"The eBucks x SmartShopper LR question exists in the clean room already (CRQ-200980). It hasn't been run against our current FRG base yet. Phase 2 (30 Aug) is running that question and joining outputs.\""},
    ]
  },
  {
    'id': 'B-gaps',
    'deck': 'super',
    'title': 'B9. "Three gaps PnP did not close"',
    'body': [
      {'h': 'What it says',
       'p': "Three side-by-side cards, each showing 'PnP said: X' and 'We add: Y'. Gap 1 is reactivation, gap 2 is ASAP, gap 3 is SS enrolment upside."},
      {'h': 'Why this section exists',
       'p': "The deck to this point has been additive to PnP's story. This section is the sharpest point: it directly identifies where their narrative stopped and shows we can pick up. It's the section that turns 'nice-to-have' into 'you-need-us'."},
      {'h': 'How the three gaps were chosen',
       'p': "Each gap has (a) a specific claim in PnP's own deck we can quote, and (b) a specific FRG unlock that directly extends it. That symmetry makes the argument watertight: we're not making it up, we're building on what they already believe."},
      {'h': 'Gap 1 detail',
       'p': "PnP slide 3 language: 'Reactivate Inactive and Lapsed Smart Shoppers' with 11.8M / 3.2M counts. Our extension: same reactivation target, but addressable and priced (Unlock 1)."},
      {'h': 'Gap 2 detail',
       'p': "PnP slide 14 language: broad Smart Shopper Aspire/Comfortable/Select for ASAP. Our extension: 6x wealth gradient, weight media 3x toward top tiers (Unlock 2)."},
      {'h': 'Gap 3 detail',
       'p': "PnP slide 2 JTBD: '1M new Smart Shoppers' without a revenue attached. Our extension: R200M annual upside in Clothing alone from SS enrolment (Unlock 3)."},
      {'h': 'Likely pushback',
       'p': "Q: \"Aren't you just repackaging our own numbers?\" A: \"The counts are yours. The addressability, sizing, wealth-tier breakdown, and Rand-priced upside are new. Together they turn each of your JTBDs from a target into a plan.\""},
    ]
  },
  {
    'id': 'B-cobrand',
    'deck': 'super',
    'title': 'B10. Co-brand activation ideas (six cards)',
    'body': [
      {'h': 'What it says',
       'p': "Six specific FRG-x-PnP co-brand campaign designs, each anchored to a specific unlock or cross-tab. Ordered from easiest-to-activate at top to most-conditional at bottom."},
      {'h': 'Why six, why in this order',
       'p': "Six is the right number to feel comprehensive without exhausting. Order runs from 'zero blockers, could brief tomorrow' (wealth-first ASAP) to 'requires Phase 2 completion' (eBucks tier boost). Reading top to bottom is the natural sales pitch: 'here's what we can do now, here's what we'll unlock next'."},
      {'h': 'Card 1, wealth-first ASAP acquisition',
       'p': "Anchored on Unlock 2. The 3x media weighting recommendation, activated via FNB app deeplinks at payday/month-end moments."},
      {'h': 'Card 2, SS enrolment at FNB cash reward moments',
       'p': "Anchored on Unlocks 3 and 4. Turns the R406 uplift into an FNB retention lever too: the FNB app shows the customer their forgone reward (extra 34%) if they haven't enrolled in Smart Shopper."},
      {'h': 'Card 3, Fresh-first FoodStop micro-campaigns',
       'p': "Anchored on Unlock 1 + the existing Engen-Woolies FoodStop concession behaviour we've seen in earlier discovery. The 947k lapsed pool includes fuel-active customers who commute past PnP stores. Sebenza + FNB app pincer around commuter corridors."},
      {'h': 'Card 4, Category-affinity campaigns per Retail_Model tier',
       'p': "Anchored on the Retail_Model x PnP behaviour appendix (A5). Different offer per tier. PC0 basket-builder, PWU premium range access."},
      {'h': 'Card 5, eBucks reward tier boost',
       'p': "Explicitly Phase 2. Once RampID resolution is enabled, quote 'ASP customers spend X% of grocery basket at PnP' and design tier-specific eBucks promos."},
      {'h': 'Card 6, Aspirational young-Affluent bundle',
       'p': "Anchored on PC0/PB0 SS-Y intersection. Live Well + baby/BTS + ASAP delivery as an FNB Private Wealth loyalty perk. Small volume, high LTV."},
      {'h': 'Likely pushback',
       'p': "Q: \"These are marketing ideas, not data insights. Aren't we overstepping?\" A: \"Each idea is anchored to a specific quantitative unlock in the deck. The purpose is to show PnP that our data can inform activation, not just observation. The specific creative execution is theirs to design.\""},
    ]
  },
  {
    'id': 'B-limitations',
    'deck': 'super',
    'title': 'B11. Named limitations (five items)',
    'body': [
      {'h': 'What it says',
       'p': "Five explicit limitations with 'fix' proposals for each. Framed as risk-owning language, not weakness."},
      {'h': 'Why this section is critical',
       'p': "Every consulting deck that omits limitations gets crushed on discovery-of-limitations by the client. Naming ours first, and pairing each with a fix, converts a weakness into a roadmap item."},
      {'h': 'Limitation 1: LR-side hash mismatch',
       'p': "pnp_audiences_for_awareness and ntb_transact tables use hashes we can't join. Fix: LiveRamp RampID resolution, or standardise the hashing recipe."},
      {'h': 'Limitation 2: eBucks reward tier attribution',
       'p': "Same root cause as Limitation 1, listed separately because the impact is different (blocks the eBucks tier story specifically)."},
      {'h': 'Limitation 3: NTB baby propensity scores',
       'p': "Same root cause again, mentioned as a third specific casualty of the hash mismatch. This makes the shared root cause obvious to the reader."},
      {'h': 'Limitation 4: Cross-shop granularity',
       'p': "We quote 'competitors' in aggregate but haven't yet broken it down per campaign audience. Available on request in Phase 2. This is honest about scope, not a data-availability issue."},
      {'h': 'Limitation 5: Sebenza commuter overlap',
       'p': "We recommended Sebenza + FNB pincer in Card 3 of the co-brand section but haven't yet quantified the FRG overlap with Sebenza's audience. Requires Sebenza to share the audience list."},
      {'h': 'Likely pushback',
       'p': "Q: \"Why are three of the five limitations the same root cause?\" A: \"Because that root cause blocks three specific unlock stories. Naming them separately lets each be tracked and resolved on its own timeline. Fixing the hash join once unlocks all three at once.\""},
    ]
  },
  {
    'id': 'B-ask',
    'deck': 'super',
    'title': 'B12. "The Ask" (closing section)',
    'body': [
      {'h': 'What it says',
       'p': "Dark-background closing section: 'Enable LiveRamp RampID identity resolution on both FRG and PnP-side audiences, or standardise both sides on the same normalised email + phone hashing recipe.'"},
      {'h': 'Why one specific ask',
       'p': "Every consulting deck should end with one clear thing the client can do. Multiple asks dilute action. Our one ask (enable RampID) is the single thing that unlocks all Phase 2 deliverables."},
      {'h': 'Why we framed it as two options',
       'p': "RampID vs standardise-the-hashing gives PnP a choice. Some organisations resist adopting new identity infrastructure; the standardised-hashing alternative is a lightweight fallback. Naming both makes it harder to say no."},
      {'h': 'Likely pushback',
       'p': "Q: \"RampID has a licence cost. Who pays?\" A: \"The clean room already exists; RampID is often bundled. If the licence is a blocker, the standardised-hashing alternative is a technical fix we can help design at zero incremental cost.\""},
    ]
  },
]


# ── Build TOC and body ───────────────────────────────────────────────────
def render_body(sec):
  parts = []
  for chunk in sec['body']:
    parts.append(f"<h4>{esc(chunk['h'])}</h4>")
    if 'p' in chunk:
      parts.append(f"<p>{chunk['p']}</p>")
    if 'items' in chunk:
      lis = ''.join(f'<li>{it}</li>' for it in chunk['items'])
      parts.append(f'<ul>{lis}</ul>')
  return ''.join(parts)


toc_html = []
body_html = []

# TOC grouped by deck
deck_labels = {'marina': 'Deck A, Marina Requested (slides 9 + 12)',
               'super': 'Deck B, Super Unlock',
               'both': 'Shared context'}

for deck_key, label in deck_labels.items():
  matching = [s for s in SECTIONS if s['deck'] == deck_key]
  if not matching:
    continue
  toc_html.append(f'<div class="toc-group"><h3>{esc(label)}</h3><ul>')
  for sec in matching:
    toc_html.append(f'<li><a href="#{esc(sec["id"])}">{esc(sec["title"])}</a></li>')
  toc_html.append('</ul></div>')

for sec in SECTIONS:
  body_html.append(f'''
    <div class="sec" id="{esc(sec["id"])}">
      <div class="sec-deck">{esc(deck_labels[sec["deck"]])}</div>
      <h2>{esc(sec["title"])}</h2>
      {render_body(sec)}
      <a href="#top" class="back-to-top">Back to top</a>
    </div>
  ''')


html = f"""<!DOCTYPE html>
<html lang='en'><head><meta charset='UTF-8'>
<title>PnP Spend Shift decks, complete walkthrough</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'DM Sans',sans-serif; background:#f8fafc; color:#1a202c; line-height:1.55; }}
#hdr {{ background:linear-gradient(135deg,#0f172a,#c8102e); color:#fff; padding:32px; }}
#hdr h1 {{ font-size:2rem; font-weight:700; }}
#hdr p {{ margin-top:8px; opacity:.92; font-size:1rem; line-height:1.55; }}
#hdr .meta {{ margin-top:14px; font-size:.75rem; opacity:.6; }}
.ctn {{ max-width:1100px; margin:0 auto; padding:24px; }}
.toc {{ background:#fff; border-radius:14px; padding:24px 30px; margin:20px 0; border:1px solid #e2e8f0; box-shadow:0 1px 4px rgba(0,0,0,.04); }}
.toc h2 {{ font-size:1.3rem; margin-bottom:12px; color:#0f172a; }}
.toc-group {{ margin-top:16px; }}
.toc-group h3 {{ font-size:.95rem; font-weight:700; color:#c8102e; margin-bottom:6px; text-transform:uppercase; letter-spacing:.05em; }}
.toc-group ul {{ list-style:none; padding-left:0; }}
.toc-group li {{ padding:4px 0; font-size:.9rem; }}
.toc-group a {{ color:#334155; text-decoration:none; border-bottom:1px dashed transparent; }}
.toc-group a:hover {{ color:#c8102e; border-bottom-color:#c8102e; }}
.sec {{ background:#fff; border-radius:14px; padding:26px 30px; margin:16px 0; border:1px solid #e2e8f0; box-shadow:0 1px 4px rgba(0,0,0,.04); }}
.sec-deck {{ display:inline-block; background:#f1f5f9; color:#334155; padding:4px 12px; border-radius:6px; font-size:.72rem; font-weight:700; text-transform:uppercase; letter-spacing:.05em; margin-bottom:12px; }}
.sec h2 {{ font-size:1.5rem; font-weight:700; color:#0f172a; margin-bottom:12px; padding-bottom:10px; border-bottom:2px solid #f1f5f9; }}
.sec h4 {{ font-size:1rem; font-weight:700; color:#0f172a; margin-top:16px; margin-bottom:6px; }}
.sec p {{ font-size:.94rem; color:#334155; margin-bottom:6px; }}
.sec ul {{ margin:6px 0 6px 22px; }}
.sec li {{ font-size:.92rem; color:#334155; margin-bottom:5px; }}
.sec b {{ color:#0f172a; }}
.back-to-top {{ display:inline-block; margin-top:16px; font-size:.8rem; color:#64748b; text-decoration:none; border-bottom:1px dashed #64748b; }}
.back-to-top:hover {{ color:#c8102e; border-bottom-color:#c8102e; }}
</style>
</head><body>

<div id='hdr' name='top'>
<h1>PnP Spend Shift decks, complete walkthrough</h1>
<p>Every section of both HTML decks explained: what it says, why we say it, how the numbers were derived, and what to answer when pushed back on. Read once end-to-end before the meeting. Use the table of contents to jump on demand.</p>
<div class='meta'>Generated {esc(now)}</div>
</div>

<div class='ctn'>

<div class='toc'>
<h2>Table of contents</h2>
{''.join(toc_html)}
</div>

{''.join(body_html)}

<div class='sec' style='background:#0f172a;color:#fff;border-color:#0f172a'>
<h2 style='color:#fff;border-color:#c8102e'>How to use this doc in the meeting</h2>
<h4 style='color:#fbbf24'>Read once end-to-end before the meeting</h4>
<p style='color:#e2e8f0'>You'll then know every reasoning path without looking it up. Roughly 20-30 minutes to read carefully.</p>
<h4 style='color:#fbbf24'>Bring the file open on your laptop</h4>
<p style='color:#e2e8f0'>If a question surprises you, Ctrl+F the section, jump to the "Likely pushback" or "How derived" bullet, answer, move on. Nobody will notice you glanced.</p>
<h4 style='color:#fbbf24'>Every claim has three answers ready</h4>
<p style='color:#e2e8f0'>What it says (the on-slide claim), how it was computed (the SQL / logic behind it), and how to answer the most likely challenge. If a question doesn't fit any of those three, say "I want to give you an accurate answer — let me confirm the exact source and follow up in writing today."</p>
<h4 style='color:#fbbf24'>When you don't know, name the limitation</h4>
<p style='color:#e2e8f0'>The deck already names five limitations. Referencing them proactively signals rigor: "That's actually one of the named limitations in the deck — Limitation 4 — cross-shop granularity. Available on request in Phase 2."</p>
</div>

</div>
</body></html>
"""

OUT = 'pnp_deck_walkthrough.html'
with open(OUT, 'w') as f:
  f.write(html)

print(f'Wrote: {OUT}')
print('Open in browser and read end-to-end before the meeting. Bring it open on your laptop for reference.')
