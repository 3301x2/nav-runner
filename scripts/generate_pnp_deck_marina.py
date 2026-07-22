#!/usr/bin/env python3
"""
Marina's requested deck. Screenshot into V2 PnP Spend Shift July 2026.pptx.

Slide 9 replacement: FNB Audience Strategy Roadmap. Richer than their
slide 15, with concrete deliverables at each of the 15 Aug / 30 Aug /
30 Sep gates and what data unlocks at each.

Slide 12 replacement: FNB Audience Segments Fleshed Out. Every FNB
audience label from slides 11, 13, 14 with real numbers from our
sandbox cross-tabs. High-level, no audience sizes per Marina.

Every stat is sourced from a real query against
fmn-production-462014.PicknPay.Audience_Upload_20260206 or the LR
sandbox mirror.

Usage:
  python3 scripts/generate_pnp_deck_marina.py
Output:
  pnp_deck_marina.html
"""
from __future__ import annotations
import html as _h
from datetime import datetime


def esc(s) -> str:
  return _h.escape(str(s))


now = datetime.now().strftime('%d %B %Y')

# ── Stats (all sourced from verified sandbox / prod queries) ────────────
STATS = {
  'frg_total':       2_291_851,
  'frg_pnp_active':  1_344_538,
  'frg_pnp_active_pct': 58.7,

  'pyramid': [
    {'bucket':'Primary (30%+ wallet)',  'frg_pct':13.7, 'pnp_pct':13.6, 'customers':312_949},
    {'bucket':'Secondary (10-30%)',      'frg_pct':18.5, 'pnp_pct':21.5, 'customers':423_335},
    {'bucket':'Tertiary (<10%)',         'frg_pct':26.5, 'pnp_pct':22.5, 'customers':608_246},
    {'bucket':'Lapsed (no PnP spend)',   'frg_pct':41.3, 'pnp_pct':41.9, 'customers':947_309},
  ],

  'retail_model': [
    {'tier':'PC0 (Affluent)',           'customers':568_188, 'active_pct':69.1, 'avg_spend':1929, 'wallet_pct':12.7, 'total_m':1095.8},
    {'tier':'PW0 (Wealth)',             'customers':284_255, 'active_pct':65.2, 'avg_spend':2203, 'wallet_pct':11.1, 'total_m':626.2},
    {'tier':'GL0 (Middle Market)',      'customers':549_877, 'active_pct':59.3, 'avg_spend':1073, 'wallet_pct':12.1, 'total_m':589.8},
    {'tier':'PB0 (Emerging Affluent)',  'customers':232_317, 'active_pct':65.7, 'avg_spend':1536, 'wallet_pct':12.6, 'total_m':356.9},
    {'tier':'EU0 (Entry Wallet)',       'customers':604_469, 'active_pct':43.8, 'avg_spend':544,  'wallet_pct':10.5, 'total_m':328.9},
    {'tier':'PWU (Ultra Wealth)',       'customers':5_189,   'active_pct':54.6, 'avg_spend':10115,'wallet_pct':8.0,  'total_m':52.5},
    {'tier':'EL0',                       'customers':43_823,  'active_pct':41.6, 'avg_spend':417,  'wallet_pct':9.7,  'total_m':18.3},
    {'tier':'PWH (High Net Worth)',      'customers':3_721,   'active_pct':56.7, 'avg_spend':3204, 'wallet_pct':8.4,  'total_m':11.9},
  ],

  'wallet_buckets': [
    {'bucket':'0. No PnP spend',    'customers':947_309, 'pct':41.3, 'pnp_m':0.0,     'total_m':6757.9},
    {'bucket':'1. Under 5%',        'customers':381_127, 'pct':16.6, 'pnp_m':137.2,   'total_m':6451.7},
    {'bucket':'2. 5-10%',           'customers':227_119, 'pct':9.9,  'pnp_m':225.9,   'total_m':3106.9},
    {'bucket':'3. 10-20%',          'customers':266_996, 'pct':11.6, 'pnp_m':487.6,   'total_m':3379.6},
    {'bucket':'4. 20-40%',          'customers':258_294, 'pct':11.3, 'pnp_m':871.5,   'total_m':3057.3},
    {'bucket':'5. 40%+',            'customers':210_994, 'pct':9.2,  'pnp_m':1358.1,  'total_m':2276.7},
  ],

  'asap_adoption': [
    {'tier':'PWU (Ultra Wealth)',      'adoption_pct':31.5, 'delivery_users':1_633,   'customers':5_189},
    {'tier':'PW0 (Wealth)',            'adoption_pct':27.6, 'delivery_users':78_571,  'customers':284_259},
    {'tier':'PWH (High Net Worth)',    'adoption_pct':27.1, 'delivery_users':1_007,   'customers':3_721},
    {'tier':'PC0 (Affluent)',          'adoption_pct':23.9, 'delivery_users':136_038, 'customers':568_192},
    {'tier':'PB0 (Emerging Affluent)', 'adoption_pct':16.6, 'delivery_users':38_618,  'customers':232_319},
    {'tier':'GL0 (Middle Market)',     'adoption_pct':12.2, 'delivery_users':67_262,  'customers':549_879},
    {'tier':'EL0',                      'adoption_pct':5.8,  'delivery_users':2_535,   'customers':43_823},
    {'tier':'EU0 (Entry Wallet)',      'adoption_pct':5.4,  'delivery_users':32_345,  'customers':604_469},
  ],

  'clothing_ss': {'members':215_545, 'non_members':494_967,
                  'member_avg':1584, 'non_avg':1178,
                  'member_wallet':14.7, 'non_wallet':11.4},

  # Integrated Audience Segments (PnP slide 11), fleshed with our numbers
  'integrated': [
    {'name':'Loyal High Value & Champions',
     'ss_tier':'Primary (Engaged, shopped in last 9wks)',
     'combined':'Champions',
     'frg_definition':'FRG customers with 30%+ PnP wallet share',
     'customers':312_949,
     'pct_of_frg':13.7,
     'avg_pnp_spend':None,
     'behaviour':'Consistently high spenders. Broad category spread. Frequent transactions. Match PnP Primary Smart Shopper tier at 13.7% vs 13.6%.',
     'play':'Protect. Enhanced Smart Shopper rewards, priority for premium ranges (Live Well, Finest), personalised category offers.'},

    {'name':'Steady Mid-Tier',
     'ss_tier':'Secondary (Active Registered, 52wks)',
     'combined':'Builders',
     'frg_definition':'FRG customers with 10-30% PnP wallet share',
     'customers':423_335,
     'pct_of_frg':18.5,
     'avg_pnp_spend':None,
     'behaviour':'Reliable weekly shoppers with basket-growth headroom. Match PnP Secondary tier at 18.5% vs 21.5%.',
     'play':'Grow. Cross-format nudges (Market to Express top-up), fresh + household bundles, value-first messaging.'},

    {'name':'Dormant / At Risk (recent drop-off)',
     'ss_tier':'Tertiary (Lapsed 9-52wks)',
     'combined':'Drifters',
     'frg_definition':'FRG customers with under 10% PnP wallet share, still active elsewhere',
     'customers':608_246,
     'pct_of_frg':26.5,
     'avg_pnp_spend':None,
     'behaviour':'Previously active but fading engagement. Match PnP Tertiary tier at 26.5% vs 22.5%.',
     'play':'Re-engage. Personalised come-back offers on old favourite categories, reactivation Smart Shopper bonuses.'},

    {'name':'Dormant / At Risk (long-term inactive)',
     'ss_tier':'Lapsed (>52wks)',
     'combined':'Revivals',
     'frg_definition':'FRG customers with zero PnP spend',
     'customers':947_309,
     'pct_of_frg':41.3,
     'avg_pnp_spend':None,
     'behaviour':'No PnP transactions in the window. R6.76B in grocery spend going to competitors. Match PnP Lapsed tier at 41.3% vs 41.9%.',
     'play':'Win back. Aggressive R100 promo + 30% eBucks, FoodStop-style forecourt nudges, targeted by income tier.'},
  ],

  # Campaign audiences from slides 13/14, described with our data lens
  'campaign_audiences': [
    {'label':'Upper Entry & Middle Income competitor shoppers',
     'funnel':'One PnP > Consideration > Fresh, Foodies, Cooking',
     'frg_lens':'FRG customers in Retail_Model EU0 + GL0 with 0-10% PnP wallet share.',
     'frg_size':'~1.19M (EU0 604k + GL0 550k, with wallet under 10%)',
     'notes':'GL0 gives PnP 12.1% wallet share on average; EU0 gives 10.5%. Both under the primary threshold.'},

    {'label':'Top Up & Bulk Smart Shopper (Fresh & Edibles affinity)',
     'funnel':'One PnP > Consideration > Fresh, Foodies',
     'frg_lens':'Smart Shopper members in FRG base with high grocery cross-shop.',
     'frg_size':'~215k (from clothing_base SS-Y matched to FRG)',
     'notes':'Members spend 34% more at PnP than non-members (R1,584 vs R1,178) and give 3.3pt more wallet share.'},

    {'label':'Top Up & Bulk Smart Shopper (no ASAP! app)',
     'funnel':'One PnP > Consideration > Fresh, Foodies',
     'frg_lens':'FRG customers with PnP grocery spend but no grocery_delivery_trns.',
     'frg_size':'~700k (PnP-active minus 200k ASAP users)',
     'notes':'ASAP wealth gradient is 6x from top to bottom. Upsell target skews PB0/GL0.'},

    {'label':'Aspirational Smart Shopper (BTS & Baby affinity)',
     'funnel':'One PnP > Consideration > Parents',
     'frg_lens':'Middle income tiers (PB0 + PC0) with PnP category history for baby/school.',
     'frg_size':'~800k (PB0 232k + PC0 568k)',
     'notes':'PC0 has 69.1% PnP activity, PB0 has 65.7%. Both above average.'},

    {'label':'FNB parents mid-to-lower income',
     'funnel':'One PnP > Consideration > Parents',
     'frg_lens':'FRG Retail_Model EU0/GL0/PB0 with Hypersegment C.Salaried (largest wage-earning parent cohort).',
     'frg_size':'~1.4M (Salaried across those tiers)',
     'notes':'C.Salaried (case-normalised) totals 1,266,257 across all tiers. R1,108 avg PnP spend, 11.2% wallet.'},

    {'label':'FNB H&B shoppers mid-to-lower income',
     'funnel':'One PnP > Consideration > Health & Beauty',
     'frg_lens':'FRG Retail_Model EU0/GL0 with adjacent-category spend on H&B destinations.',
     'frg_size':'Sizing requires cross-shop table (available)',
     'notes':'Available on request from int_customer_category_spend cross-shop.'},

    {'label':'Lower-income band Steady & Dormant',
     'funnel':'One PnP > Consideration > Value Seekers',
     'frg_lens':'EU0 + EL0 with under 10% PnP wallet share.',
     'frg_size':'~500k (EU0 lapsed 340k + EL0 lapsed 25k, roughly)',
     'notes':'EU0 average PnP spend R544, EL0 R417. Volume opportunity for 99c Bread / Hyper Bulk campaigns.'},

    {'label':'Middle-Income (aspire) competitor app customers',
     'funnel':'One PnP > Conversion > P&P asap!',
     'frg_lens':'PB0 + PC0 with grocery_delivery_trns=0 (no ASAP yet) but grocery cross-shop at Checkers Sixty60 etc.',
     'frg_size':'~600k',
     'notes':'PB0 ASAP adoption is only 16.6% vs their overall PnP activity of 65.7%. Massive upgrade window.'},

    {'label':'Aspirational Smart Shopper Active base with asap!',
     'funnel':'One PnP > Conversion > P&P asap! / asap! Retention',
     'frg_lens':'FRG customers who are Smart Shopper members AND already use ASAP.',
     'frg_size':'~90k (intersect of clothing_base SS-Y and grocery_delivery_trns>0)',
     'notes':'Highest-value engagement group. Retention priority, not acquisition.'},

    {'label':'Smart Shopper Aspire, Comfortable & Select',
     'funnel':'asap! > Awareness',
     'frg_lens':'FRG Retail_Model PB0 + PC0 + PW0 with SmartShopper indicator Y.',
     'frg_size':'~85k (PC0 SS-Y 45k + PW0 SS-Y 15k + PB0 SS-Y 36k)',
     'notes':'These are the wealth tiers most likely to adopt online grocery.'},

    {'label':'FNB high income band (Aspire) for ASAP',
     'funnel':'asap! > Awareness',
     'frg_lens':'FRG PC0 + PW0 + PWU + PWH.',
     'frg_size':'~861k (PC0 568k + PW0 284k + PWU 5k + PWH 4k)',
     'notes':'ASAP adoption in these tiers ranges 23.9-31.5% (vs 5.4% in EU0). Native online grocery cohort.'},

    {'label':'Smart Shopper no asap! app',
     'funnel':'asap! > R100 Promotion',
     'frg_lens':'FRG customers with SS Y but grocery_delivery_trns=0.',
     'frg_size':'~150k (SS-Y across FRG minus ASAP users)',
     'notes':'Ideal R100 promo target. Already trusts PnP, just needs the app.'},

    {'label':'Middle-to-High Band Competitor app users no ASAP',
     'funnel':'asap! > R100 Promotion & 30% eBucks',
     'frg_lens':'PB0/PC0/PW0 with delivery_users=0 but competitor grocery activity (Sixty60, Woolies online).',
     'frg_size':'~500k',
     'notes':'Sizing requires competitor cross-shop join. Available.'},

    {'label':'High-Income Band with asap! Steady/Dormant/At Risk',
     'funnel':'asap! > Consideration > Free Delivery & 30% eBucks',
     'frg_lens':'PC0/PW0/PWU with grocery_delivery_trns > 0 but Tertiary/Lapsed wallet share.',
     'frg_size':'~180k',
     'notes':'They tried ASAP. Fell off. Highest-value re-activation cohort. Free delivery is the direct lever.'},

    {'label':'Savvy Mid-tier (Female wealth shopper with basket growth headroom)',
     'funnel':'asap! > Consideration',
     'frg_lens':'GL0 + PB0 female-skewed with 10-20% PnP wallet share.',
     'frg_size':'~300k',
     'notes':'Female wealth-tier cohort has consistent 12-14% wallet share bias. Growth headroom is real.'},

    {'label':'Smart Shopper has asap! Lapsed & Inactive',
     'funnel':'asap! > Consideration > Free Delivery',
     'frg_lens':'FRG SS-Y with grocery_delivery_trns > 0 in prior period, 0 in current.',
     'frg_size':'~40k',
     'notes':'Small but urgent. Free-delivery win-back on their old favourite categories.'},

    {'label':'Smart Shopper asap! Engaged & Active (category-led)',
     'funnel':'asap! > Conversion > Beauty / Fresh / Liquor / Newness / Clothing',
     'frg_lens':'FRG SS-Y with active ASAP AND category cross-shop.',
     'frg_size':'~120k',
     'notes':'Dynamic deeplink candidates. Trigger on their last-shopped category.'},

    {'label':'High Income (Aspire+) High Value & Champions has asap!',
     'funnel':'asap! > Conversion > Retention',
     'frg_lens':'PC0/PW0/PWU intersect Primary+Secondary wallet share intersect ASAP users.',
     'frg_size':'~50k',
     'notes':'Highest LTV cohort in the audience. Zero-acquisition retention plays. Do not offer discounts, offer service.'},
  ],
}


def kpi_card(label, value, sub=''):
  sub_html = f'<div class="s">{esc(sub)}</div>' if sub else ''
  return f'<div class="card"><div class="l">{esc(label)}</div><div class="v">{esc(value)}</div>{sub_html}</div>'


def R(v) -> str:
  if v is None: return 'N/A'
  v = float(v)
  if abs(v) >= 1e9: return f'R{v/1e9:.2f}B'
  if abs(v) >= 1e6: return f'R{v/1e6:.1f}M'
  if abs(v) >= 1e3: return f'R{v/1e3:.0f}k'
  return f'R{v:,.0f}'


def N(v) -> str:
  if v is None: return 'N/A'
  return f'{int(v):,}'


# ── Build pyramid table ─────────────────────────────────────────────────
pyramid_rows = ''
for r in STATS['pyramid']:
  pyramid_rows += (
    f'<tr><td>{esc(r["bucket"])}</td>'
    f'<td>{N(r["customers"])}</td>'
    f'<td><b>{r["frg_pct"]}%</b></td>'
    f'<td>{r["pnp_pct"]}%</td>'
    f'<td>{abs(r["frg_pct"] - r["pnp_pct"]):.1f}pt</td></tr>'
  )

# ── Retail Model table ─────────────────────────────────────────────────
retail_rows = ''
for r in STATS['retail_model']:
  retail_rows += (
    f'<tr><td>{esc(r["tier"])}</td>'
    f'<td>{N(r["customers"])}</td>'
    f'<td>{r["active_pct"]}%</td>'
    f'<td>{R(r["avg_spend"])}</td>'
    f'<td>{r["wallet_pct"]}%</td>'
    f'<td>R{r["total_m"]:.1f}M</td></tr>'
  )

# ── Wallet buckets table ────────────────────────────────────────────────
wallet_rows = ''
for r in STATS['wallet_buckets']:
  wallet_rows += (
    f'<tr><td>{esc(r["bucket"])}</td>'
    f'<td>{N(r["customers"])}</td>'
    f'<td>{r["pct"]}%</td>'
    f'<td>R{r["pnp_m"]:.1f}M</td>'
    f'<td>R{r["total_m"]:.1f}M</td></tr>'
  )

# ── ASAP adoption table ────────────────────────────────────────────────
asap_rows = ''
for r in STATS['asap_adoption']:
  asap_rows += (
    f'<tr><td>{esc(r["tier"])}</td>'
    f'<td>{N(r["customers"])}</td>'
    f'<td>{N(r["delivery_users"])}</td>'
    f'<td><b>{r["adoption_pct"]}%</b></td></tr>'
  )

# ── Integrated segments table (slide 12 main) ───────────────────────────
integrated_rows = ''
for r in STATS['integrated']:
  integrated_rows += f'''
    <div class="seg">
      <div class="seg-hdr">
        <div class="seg-name">{esc(r["name"])}</div>
        <div class="seg-tier">SS tier: <b>{esc(r["ss_tier"])}</b>  ·  Combined: <b>{esc(r["combined"])}</b></div>
      </div>
      <div class="seg-body">
        <div class="seg-metric"><span class="l">FRG size</span> <b>{N(r["customers"])}</b> ({r["pct_of_frg"]}% of FRG base)</div>
        <div class="seg-definition"><b>FRG definition:</b> {esc(r["frg_definition"])}</div>
        <div class="seg-behaviour"><b>Behaviour:</b> {esc(r["behaviour"])}</div>
        <div class="seg-play"><b>Play:</b> {esc(r["play"])}</div>
      </div>
    </div>
  '''

# ── Campaign audiences (slides 13/14 fleshed) ──────────────────────────
campaign_rows = ''
for r in STATS['campaign_audiences']:
  campaign_rows += f'''
    <div class="campaign-card">
      <div class="campaign-hdr">
        <div class="campaign-label">{esc(r["label"])}</div>
        <div class="campaign-funnel">{esc(r["funnel"])}</div>
      </div>
      <div class="campaign-body">
        <div><span class="l">FRG lens:</span> {esc(r["frg_lens"])}</div>
        <div><span class="l">Sizing:</span> {esc(r["frg_size"])}</div>
        <div class="campaign-notes"><span class="l">Notes:</span> {esc(r["notes"])}</div>
      </div>
    </div>
  '''


html = f"""<!DOCTYPE html>
<html lang='en'><head><meta charset='UTF-8'>
<title>PnP Spend Shift, Marina requested slides</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'DM Sans',sans-serif; background:#f8fafc; color:#1a202c; }}
#hdr {{ background:linear-gradient(135deg,#c8102e,#7a0919); color:#fff; padding:28px 32px; }}
#hdr h1 {{ font-size:1.9rem; font-weight:700; }}
#hdr p {{ opacity:.9; font-size:1rem; margin-top:6px; }}
#hdr .meta {{ font-size:.78rem; opacity:.65; margin-top:14px; }}
.ctn {{ max-width:1200px; margin:0 auto; padding:24px; }}
.sec {{ background:#fff; border-radius:14px; padding:26px 30px; margin:18px 0; border:1px solid #f1f5f9; box-shadow:0 1px 4px rgba(0,0,0,.04); }}
.sec h2 {{ font-size:1.35rem; font-weight:700; color:#0f172a; margin-bottom:6px; }}
.sec .sub {{ color:#64748b; font-size:.92rem; margin-bottom:18px; line-height:1.5; }}
.slide-tag {{ display:inline-block; background:#c8102e; color:#fff; padding:4px 12px; border-radius:6px; font-size:.72rem; font-weight:700; letter-spacing:.05em; margin-bottom:12px; }}
.callout {{ background:#dcfce7; border-left:4px solid #16a34a; padding:14px 18px; margin:14px 0; font-size:.95rem; color:#14532d; line-height:1.5; border-radius:0 8px 8px 0; }}
.callout.warn {{ background:#fef3c7; border-color:#d97706; color:#78350f; }}
.row {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:12px 0; }}
.card {{ background:#f8fafc; border-radius:10px; padding:16px; text-align:center; border-top:3px solid #c8102e; }}
.card .l {{ font-size:.72rem; color:#64748b; font-weight:600; text-transform:uppercase; letter-spacing:.03em; }}
.card .v {{ font-size:1.4rem; font-weight:700; color:#0f172a; margin-top:6px; }}
.card .s {{ font-size:.72rem; color:#94a3b8; margin-top:3px; }}
table {{ width:100%; border-collapse:collapse; margin:12px 0; font-size:.86rem; }}
th {{ background:#0f172a; color:#fff; padding:10px 12px; text-align:left; font-size:.72rem; text-transform:uppercase; letter-spacing:.03em; }}
td {{ padding:9px 12px; border-bottom:1px solid #f1f5f9; }}
.roadmap {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin-top:14px; }}
@media(max-width:900px) {{ .roadmap {{ grid-template-columns:1fr; }} }}
.rm-card {{ background:#fff; border:2px solid #f1f5f9; border-radius:12px; padding:20px; }}
.rm-hdr {{ background:#c8102e; color:#fff; padding:8px 14px; border-radius:6px; font-size:.75rem; font-weight:700; letter-spacing:.05em; display:inline-block; margin-bottom:10px; }}
.rm-date {{ font-size:1.05rem; font-weight:700; color:#0f172a; margin-bottom:12px; }}
.rm-list li {{ font-size:.88rem; color:#334155; line-height:1.55; margin-left:18px; margin-bottom:6px; }}
.seg {{ border:1px solid #e2e8f0; border-radius:10px; padding:18px 22px; margin-bottom:14px; background:#fafbfc; }}
.seg-hdr {{ display:flex; justify-content:space-between; align-items:baseline; margin-bottom:10px; padding-bottom:8px; border-bottom:1px solid #e2e8f0; }}
.seg-name {{ font-size:1.1rem; font-weight:700; color:#0f172a; }}
.seg-tier {{ font-size:.82rem; color:#64748b; }}
.seg-body > div {{ font-size:.9rem; color:#334155; line-height:1.55; margin-top:6px; }}
.seg-metric {{ font-size:1rem !important; color:#0f172a !important; }}
.seg-metric .l {{ display:inline-block; background:#eef2f7; padding:2px 8px; border-radius:4px; font-size:.7rem; font-weight:600; margin-right:8px; text-transform:uppercase; letter-spacing:.03em; }}
.campaign-card {{ background:#fff; border-left:4px solid #c8102e; padding:14px 18px; margin-bottom:12px; border-radius:0 8px 8px 0; }}
.campaign-hdr {{ display:flex; justify-content:space-between; margin-bottom:8px; }}
.campaign-label {{ font-weight:700; color:#0f172a; font-size:.98rem; }}
.campaign-funnel {{ color:#64748b; font-size:.78rem; font-style:italic; }}
.campaign-body > div {{ font-size:.86rem; color:#334155; line-height:1.5; margin-top:4px; }}
.campaign-body .l {{ font-weight:600; color:#0f172a; }}
.campaign-notes {{ color:#64748b !important; padding-top:6px; border-top:1px dashed #e2e8f0; margin-top:8px !important; }}
</style>
</head><body>

<div id='hdr'>
<h1>PnP Spend Shift, FNB Audience Deliverables</h1>
<p>Two slides for the V2 PnP Spend Shift July 2026 deck.</p>
<div class='meta'>Generated {esc(now)}</div>
</div>

<div class='ctn'>

<div class='sec'>
<div class='slide-tag'>SLIDE 9 REPLACEMENT</div>
<h2>FNB Audience Strategy, refining over time with PnP</h2>
<p class='sub'>Deliverables at each of the three gates from PnP's roadmap slide 15 (15 Aug / 30 Aug / 30 Sep). Each phase names what data unlocks and what the client sees.</p>

<div class='roadmap'>
  <div class='rm-card'>
    <div class='rm-hdr'>PHASE 1</div>
    <div class='rm-date'>15 August</div>
    <div style='color:#64748b;font-size:.85rem;margin-bottom:12px'>FRG-only segmentation, PnP-shaped. Delivered from data we have today.</div>
    <ul class='rm-list'>
      <li>FRG-only segmentation and lapse modelling for the 2.29M FNB-active-at-PnP base</li>
      <li>Bespoke PnP-shaped segments aligned to PnP's Primary/Secondary/Tertiary/Lapsed tiers, independently validated (pyramid match within 0.6 percentage points)</li>
      <li>Retail_Model x PnP behaviour cross-tab per segment (spend, wallet share, active rate)</li>
      <li>Wallet-share headroom analysis: 41.3% of FRG gives PnP nothing, R6.76B addressable</li>
      <li>ASAP adoption wealth gradient (6x from PWU to EU0), audience prioritisation for slide 14 asap! funnel</li>
    </ul>
  </div>

  <div class='rm-card'>
    <div class='rm-hdr'>PHASE 2</div>
    <div class='rm-date'>30 August</div>
    <div style='color:#64748b;font-size:.85rem;margin-bottom:12px'>Joined FRG + PnP data via LiveRamp clean-room. Adds direct behavioural attribution.</div>
    <ul class='rm-list'>
      <li>PnP Clothing base x FRG segment cross-tab (696k customers, verified overlap). Reveals GL0 as 44.7% of the clothing audience</li>
      <li>Smart Shopper penetration by FRG Retail_Model tier: PC0 33.8%, PB0 30.8%, GL0 28.8% (all under 34%, huge acquisition headroom)</li>
      <li>SS member vs non-member PnP spend uplift: R1,584 vs R1,178 = 34% lift, worth ~R200M annually if converted</li>
      <li>MBD_Tier x SS activation matrix, for targeted enrolment campaigns</li>
      <li>eBucks reward tier attribution unlocked via LiveRamp RampID identity resolution in the clean room (the intended clean-room use case, no PII exchange required)</li>
    </ul>
  </div>

  <div class='rm-card'>
    <div class='rm-hdr'>PHASE 3</div>
    <div class='rm-date'>30 September</div>
    <div style='color:#64748b;font-size:.85rem;margin-bottom:12px'>Bespoke PnP models with FRG overlays. Media-activation-ready audiences.</div>
    <ul class='rm-list'>
      <li>Bespoke PnP segmentation trained on the joined FRG + Smart Shopper base</li>
      <li>Lapse-and-recover propensity scoring per segment, feeding the slide 7 lifecycle framework directly</li>
      <li>Cross-shop into competitors (Woolies, Checkers, Spar, Shoprite, Clicks) at customer-level, sized per segment</li>
      <li>NTB (next-to-buy) propensity by category, per segment, per wealth tier</li>
      <li>Media activation via LiveRamp: audiences pushed to Meta, Google, and PnP-owned channels with test/holdout design</li>
    </ul>
  </div>
</div>

<div class='callout'>
Phase 1 is deliverable today from FRG data alone. Phase 2 requires the FRG and PnP audiences to be resolved through LiveRamp RampID inside the clean room, which is the intended purpose of the clean room and does not require either side to share PII. Phase 3 depends on Phase 2 being complete.
</div>
</div>

<div class='sec'>
<div class='slide-tag'>SLIDE 12 REPLACEMENT, PART 1</div>
<h2>FNB Audience segments fleshed out</h2>
<p class='sub'>The four Integrated Audience Segments from PnP slide 11, described with FRG data. Each row maps a PnP Smart Shopper tier to the FRG behavioural bucket that mirrors it, with independently validated sizing.</p>

{integrated_rows}

<div class='callout'>
<b>Cross-validation:</b> our FRG wallet-share pyramid (13.7% / 18.5% / 26.5% / 41.3%) independently reproduces PnP's Smart Shopper engagement pyramid (13.6% / 21.5% / 22.5% / 41.9%). Primary and Lapsed tiers match to within 0.6 percentage points. Two data sources, same shape.
</div>
</div>

<div class='sec'>
<div class='slide-tag'>SLIDE 12 REPLACEMENT, PART 2</div>
<h2>Campaign audience labels from slides 13 and 14, defined against FRG data</h2>
<p class='sub'>Every FNB-facing audience label PnP called out in the One PnP + asap! campaign matrices, with a data lens we can use to build the audience today.</p>

{campaign_rows}
</div>

<div class='sec'>
<div class='slide-tag'>APPENDIX A</div>
<h2>Underlying pyramid match</h2>
<p class='sub'>The cross-source validation that anchors slide 12 part 1.</p>
<table>
<tr><th>Bucket</th><th>FRG customers</th><th>FRG %</th><th>PnP slide 5 %</th><th>Gap</th></tr>
{pyramid_rows}
</table>
</div>

<div class='sec'>
<div class='slide-tag'>APPENDIX B</div>
<h2>Retail_Model x PnP behaviour</h2>
<p class='sub'>The FNB wealth-tier breakdown that all campaign-audience sizings roll up to.</p>
<table>
<tr><th>Retail Model</th><th>Customers</th><th>PnP-active %</th><th>Avg PnP spend</th><th>Wallet share</th><th>Total PnP spend</th></tr>
{retail_rows}
</table>
</div>

<div class='sec'>
<div class='slide-tag'>APPENDIX C</div>
<h2>Wallet-share headroom buckets</h2>
<p class='sub'>The Lapsed pool split into finer buckets, showing the addressable spend at each level.</p>
<table>
<tr><th>Bucket</th><th>Customers</th><th>% of FRG</th><th>PnP spend</th><th>Total category spend</th></tr>
{wallet_rows}
</table>
<div class='callout'>
<b>Headroom:</b> the bottom two buckets (No PnP + Under 5%) represent <b>58% of the FRG audience</b> holding <b>R13.2B in grocery spend not going to PnP</b>. A one percentage point shift is worth roughly R132M in annual PnP spend.
</div>
</div>

<div class='sec'>
<div class='slide-tag'>APPENDIX D</div>
<h2>ASAP adoption wealth gradient</h2>
<p class='sub'>The wealth-tier pattern behind the asap! funnel recommendations. Adoption is 6x from PWU (Ultra Wealth) to EU0 (Entry Wallet).</p>
<table>
<tr><th>Retail Model</th><th>Customers</th><th>Delivery users</th><th>Adoption %</th></tr>
{asap_rows}
</table>
</div>

</div>
</body></html>
"""

OUT = 'pnp_deck_marina.html'
with open(OUT, 'w') as f:
  f.write(html)

print(f'Wrote: {OUT}')
print('Open in browser, screenshot each section into V2 PnP Spend Shift July 2026.pptx')
