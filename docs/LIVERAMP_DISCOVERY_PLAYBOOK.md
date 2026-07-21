# LiveRamp Discovery Playbook, FRB x Pick N Pay Collaboration clean room

Goal: inventory everything the clean room exposes to us so we can decide what
insights it unlocks for the Tuesday PnP deck. This is a UI walkthrough for
the LiveRamp clean room, not a nav-runner script. Screenshot each step and
we consolidate into a single map.

Cleanroom: FRB x Pick N Pay Collaboration.

## Phase 1, Datasets and schemas (30 min)

### 1. List every dataset in the clean room

- Nav to Destinations tab or Data tab (bottom-left toggle).
- Screenshot the full list. Note two columns: owner (FRB vs PnP) and dataset
  name.
- Expected FRB-side: FNB customer base, transaction base, MB (main-banked)
  base, RAFE features, eBucks base, WesBank orphan audiences.
- Expected PnP-side: Smart Shopper base, ASAP customers, Clothing base,
  campaign response tables. Screenshot confirms.

### 2. For each dataset, list columns and row count

- Click into a dataset. Look for a schema/details panel.
- Screenshot for every dataset. Priority order:
  1. PnP Smart Shopper base (this is what we do NOT have on our side)
  2. PnP ASAP customers
  3. PnP Clothing base
  4. Any PnP campaign response table
  5. eBucks x PnP linkage tables
- We especially want to know:
  - Is there a Smart Shopper tier column (Primary/Secondary/Tertiary/Lapsed)?
  - Is there a category spend column (Fresh/Edibles/Non-edibles/Liquor/GMD)?
  - Is there a "last shop date" column? A "shop frequency" column?
  - What is the identity resolution key on the PnP side? (Hashed email?
    Hashed phone? RampID? Both?)
  - What is the join key we can use to bridge FRB customers to PnP customers?

### 3. Reverse map on the FRB side

- Same schema-inventory exercise for every FRB dataset in the clean room.
- We want to confirm which of our sandbox tables (`fmn-sandbox.staging.*`,
  `fmn-sandbox.analytics.*`) are actually mirrored into the clean room vs
  only available on our side.

## Phase 2, Questions and Reports (30 min)

### 4. Open every existing Question and screenshot the output

There are 32 questions. Priority ones based on their names:

- CRQ-200980 `eBucks x Pnp SmartSho...` (this is likely the goldmine)
- CRQ-200982 `pnp_ebucks_test`
- CRQ-214722 `pnp_ebucks_test - Clone`
- CRQ-183007 `FAds Audience Overlap`
- CRQ-183005 `Omnisient POC - eBucks...`
- CRQ-181400, CRQ-181395 `PnP POC Campaign - FN...`
- CRQ-183800 `PnP-POC Campaign - FN...`
- CRQ-189448 `PnP Audiences for Awar...`
- CRQ-189444 `PNP clothing base`
- CRQ-178049 `Overlap of FNB MB base...`
- CRQ-189445 `WesBank orphan audien...`

For each, screenshot:
  a. The SQL/logic (if visible)
  b. The last-run result (the green "Report" button opens it)
  c. The tag/category

### 5. Note the shape of every question

We want a running list of:
- Question ID
- Purpose in plain English
- Which datasets it joins
- What identity resolution it uses
- What output shape (a count, a list, an audience, a distribution)
- When it was last run

This becomes the "what we already have" section of the discovery report.

## Phase 3, Destinations and Flows (15 min)

### 6. Screenshot the Destinations tab

We saw 26 exports. We want to know:
- Which ones are still live vs archived
- Where each one lands (GCS bucket path, S3 bucket path, GoogleAds account,
  Meta account)
- The naming convention so we can request a new destination without
  breaking Rory's existing setup

### 7. Screenshot Flows

Flows tie questions to destinations. We want the run history: which flows
have fired recently, which are broken, which are one-shot vs recurring.

## Phase 4, The "what does LiveRamp actually unlock" summary

Once phases 1-3 are done, we write a single-page report:

  Section A: What FRB data is in LR that we ALSO have in nav-runner sandbox
             (so LR gives us nothing new for this).
  Section B: What FRB data is in LR that we do NOT have in nav-runner
             (LR is the only route).
  Section C: What PnP data is in LR (this is the whole reason we care).
             Break down: Smart Shopper tiers, ASAP, Clothing, campaigns.
  Section D: What identity resolution keys are shared. This determines what
             joins are legal.
  Section E: For each of the PnP framework segments (Active/Lapsed/Inactive
             x Primary/Secondary/Tertiary x High-spender/Low-SOW/No-PnP-spend
             x Fresh/Edibles/Non-edibles/Liquor/GMD), can we compute it from
             the LR joins? Yes/No/Only-partially.

## The Tuesday deck (slide 9 and slide 12) is built AFTER Section E

Slide 9 (roadmap) writes itself once we know what LR can/cannot do:
  - Phase 1 (Tuesday): what we already know from FRG data only (nav-runner)
  - Phase 2 (in 1 week): first LR overlaps we can run
  - Phase 3 (in 4 weeks): richer joins as we learn the schema
  - Phase 4 (in 8 weeks): closed-loop measurement, campaign attribution

Slide 12 (segment fleshing) writes itself too, once we know which columns
exist on which side, and which segments are computable.

## Time estimate

Phases 1-3: 1.25 hours if the UI is responsive and you screenshot as you
go. Phase 4 write-up: another hour to consolidate into the inventory doc.
Total: half a working day. Then the deck is 4 hours on top of that.

## Deliverable path

Screenshot each phase into `~/Downloads/`, drop the discovery notes into
`nav-runner/docs/liveramp_inventory.md` (create it), and I will assemble the
Tuesday deck slides 9 + 12 from that.
