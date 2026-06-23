# Property Tax Appeal Forge

Build a filing-ready property tax appeal packet from an address — the same deliverable contingency services like Owlue and Ownwell charge 25% of first-year savings for.

**v1 covers King County, WA.** The jurisdiction layer is designed to be swappable.

## What it does

Given a residential property address, the pipeline:

1. **Resolves the parcel** — address → PIN via King County ArcGIS
2. **Pulls assessed values** — current assessment, land/improvement split, building characteristics, levy rate
3. **Finds comparable sales** — arm's-length sales within ±18 months, filtered by location, size, grade
4. **Adjusts each comp** — time, living area, grade, age, bedrooms, bathrooms → adjustment grid
5. **Tests the case** — is there an over-assessment? How much would you save?
6. **Builds the packet** — pre-filled petition fields, evidence narrative with comp grid, filing deadline

## Quick start

```bash
# Clone
git clone https://github.com/yourusername/property-tax-appeal-forge.git
cd property-tax-appeal-forge

# One-time: download King County data extracts (~180MB download, ~880MB on disk)
bash scripts/setup.sh

# Run for any King County address
bash scripts/run_appeal.sh "1817 Morris Ave S, Renton, WA 98055"
```

Output lands in `run/<PIN>/`:
- `petition.json` — pre-filled eAppeals petition fields
- `evidence_packet.md` — comp grid, adjustments, opinion of value
- `deadline.md` — filing deadline based on KC mailing schedule
- `decision.json` — go/no-go with savings estimate
- Plus: `subject.json`, `comps.json`, `valuation.json`, `parcel.json`

## As a Claude Code skill

Drop this repo into your Claude Code skills directory and it triggers on:
- "Appeal my property tax"
- "Is my assessment too high?"
- "How much could I save by appealing?"
- Any King County address + a question about property value

## Requirements

- Python 3.10+
- Network access to `kingcounty.gov` and `gismaps.kingcounty.gov`
- ~1GB disk for the KC assessor data extracts (downloaded automatically)
- No API keys, no paid services, no dependencies beyond Python stdlib

## How it works

The appeal is built on the **sales comparison approach** — the same method the assessor uses. For each comparable sale, adjustments account for how the comp differs from the subject (size, grade, age, bedrooms, bathrooms). The adjusted prices form a range; the opinion of value is the conservative low end.

The pipeline uses only **admissible evidence** per WAC 458-14-056(5). It deliberately excludes everything the Board of Appeals cannot consider: assessment-to-assessment comparisons, tax increase percentages, personal hardship, or the dollar amount of tax.

### Data sources

All public, no API keys needed:

| Data | Source | Method |
|---|---|---|
| Address → PIN | [ArcGIS ParcelAddress geocoder](https://gismaps.kingcounty.gov/arcgis/rest/services/Address/KingCo_ParcelAddress_locator/GeocodeServer) | REST query |
| Assessed values | [eRealProperty Dashboard](https://blue.kingcounty.com/Assessor/eRealProperty/) | HTML parse |
| Building characteristics | eRealProperty Dashboard | HTML parse |
| Levy rate | eRealProperty levy distribution | HTML parse |
| Comparable sales | [KC Assessor data extracts](https://info.kingcounty.gov/assessor/datadownload/default.aspx) | Local CSV |
| Filing deadline | [KC notice mailing schedule](https://kingcounty.gov/en/dept/assessor/buildings-and-property/property-value-and-information/reports/area-reports/) | Published by area |

## Example output

**1817 Morris Ave S, Renton WA 98055** (PIN 7222000353):

```
Assessed:        $536,000
Opinion:         $491,000
Over-assessment: $45,000 (8.4%)
Est. tax saving: $476/year
Deadline:        July 28, 2025

Comp grid: 8 arm's-length sales, adjusted range $439K–$635K
Strongest comps: 1.8% and 2.9% gross adjustment
```

## Disclaimers

- **Not legal or tax advice.** Decision-support and document preparation only.
- **Estimates until validated.** Confirm against the actual valuation notice and certified tax roll.
- **Owner owns the filing.** The property owner is responsible for accuracy and meeting the deadline.
- **No outcome guarantee.** ~25% of KC appeals receive a reduction.

## License

MIT
