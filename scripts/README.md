# Scripts — build status

## Built and tested (2026-06-23)

1. **resolve_parcel.py** — `address → PIN`. Uses KC ArcGIS ParcelAddress geocoder. Also fetches
   zoning/lot/use from the PropertyInfo layer. Tested with 1817 Morris Ave S, Renton → PIN 7222000353.

2. **fetch_account_value.py** — `PIN → assessed value + characteristics + levy rate`. Parses the
   eRealProperty Dashboard HTML (server-side rendered, no JS needed). Merges into `subject.json`.
   Tested: $536K assessed, 1140 sqft, grade 7, levy code 2100, rate 1.058%.

3. **fetch_comps.py** — Candidate comparable sales from locally-cached KC extracts (`EXTR_RPSale.csv`
   + `EXTR_ResBldg.csv`). Filters: ±18mo time window, ±30% sqft, ±2 grade, arm's-length only.
   Scores by similarity, flags opposing comp. **Requires extracts in `extracts/` directory.**

4. **download_extracts.sh** — Opens the KC data download page in browser. User must accept disclaimer
   and download three CSVs to `extracts/`. One-time setup, refresh weekly.

5. **adjust_and_value.py** — Adjustment grid → indicated range → opinion of value. Reads `comps.json`
   and `subject.json`. Market-supported rates for KC residential. Flags opposing comp with
   distinguishing note. Writes `valuation.json`.

6. **case_test.py** — Over-assessment delta + effective rate → go/no-go. Reads `subject.json` and
   `valuation.json`. Writes `decision.json`.

7. **build_packet.py** — Render `petition.json` (pre-filled eAppeals fields), `evidence_packet.md`
   (comp grid + reconciliation), and `deadline.md`. Reads all prior artifacts.

## Run order

```bash
# One-time: download extracts (or curl directly from aqua.kingcounty.gov/extranet/assessor/)
bash scripts/download_extracts.sh

# Per-parcel pipeline
python3 scripts/resolve_parcel.py "1817 Morris Ave S, Renton, WA 98055" run/7222000353
python3 scripts/fetch_account_value.py 7222000353 run/7222000353
python3 scripts/fetch_comps.py run/7222000353
python3 scripts/adjust_and_value.py run/7222000353
python3 scripts/case_test.py run/7222000353
python3 scripts/build_packet.py run/7222000353
```

## Data sources (verified)

| Data | Source | Method |
|---|---|---|
| Address → PIN | ArcGIS ParcelAddress geocoder | REST JSON query |
| Zoning/lot/use | ArcGIS PropertyInfo MapServer | REST JSON query |
| Assessed values | eRealProperty Dashboard | HTML parse (server-rendered) |
| Building characteristics | eRealProperty Dashboard | HTML parse |
| Levy rate | eRealProperty levy distribution | HTML parse |
| Comparable sales | EXTR_RPSale.csv extract | Local CSV query |
| Building data (comps) | EXTR_ResBldg.csv extract | Local CSV query |

## End-to-end test parcel

`7222000353` (1817 Morris Ave S, Renton WA 98055). Run output in `run/7222000353/`.
