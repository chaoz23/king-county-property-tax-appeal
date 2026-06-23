# Jurisdiction Profile: King County, Washington

Authority: King County Board of Appeals & Equalization (BOE), an independent agency, **not** the
Assessor. WA statewide framework under RCW 84.40 / WAC 458-14.

## Deadline rule

File by the **later of**:
- July 1 of the assessment year, **or**
- 60 calendar days from the mailing date printed on the valuation/change-of-value notice.

The assessment year is the year **before** the tax is due (a 2026 assessment sets 2027 taxes).
King County mails valuation notices in rolling waves, roughly May through November, grouped by
area, so for most owners the 60-day clock — not July 1 — is the operative deadline and can fall
well after July 1.

**Notice mailing schedule (public, by area):**
`https://kingcounty.gov/en/dept/assessor/buildings-and-property/property-value-and-information/reports/area-reports/{year}/residential-notice-mailing-date`
Replace `{year}` with the assessment year. Cross-reference with the parcel's area code from the
ArcGIS PropertyInfo layer (`PREUSE_CODE` or area number from eSales). This is how contingency
services (Owlue, Ownwell) determine the deadline without the owner's notice in hand.

> Discrepancy to be aware of: some third-party sites state July 1 is a hard cap. The official King
> County BOE language is "latter of July 1 or 60 days," i.e. 60 days can extend past July 1. Use
> the official rule; when in doubt, look up the parcel's appeal due date on the portal, which
> displays the exact date for that parcel.

Missing the window almost always forecloses appeal until the next cycle (limited statutory
exceptions exist for prior years).

## Evidence rule (admissibility)

- **RCW 84.40.030** — property assessed at 100% of true and fair market value as of Jan 1.
- **RCW 84.40.038** — right and procedure to petition the BOE.
- **WAC 458-14-056(5)** — the petition must state why the assessor's value does not reflect true
  and fair market value. The board CANNOT consider: assessment-to-assessment comparisons with other
  properties, percentage value increases, personal hardship, or the amount of tax. Only
  market-value evidence (sales, appraisal, condition, record corrections).

## Process timeline after filing

- File via **eAppeals** (online portal) — recommended over mail; email confirmation within 24h;
  one petition **per parcel**.
- Both parties must exchange any additional evidence with the BOE **and** the other party at least
  **21 business days** before the hearing. The Assessor does not forward your evidence for you.
- Hearings are generally scheduled ~45 days out, in order received; completing evidence submission
  early can qualify for an expedited hearing.
- BOE issues a written decision within ~45 days of the hearing.
- Either party may appeal to the **WA State Board of Tax Appeals within 30 days** of the decision.
- Pay the existing tax bill on schedule (first half Apr 30, second half Oct 31) while pending; a
  win yields a corrected bill or a refund, processed over a couple of months.

Base rate context: per King County, roughly **25%** of appealed values receive some reduction. Do
not promise outcomes.

## Data sources (machine-readable — prefer these over the eReal Property dashboard)

The eReal Property dashboard (`blue.kingcounty.com/Assessor/eRealProperty/...`) is JavaScript-
rendered and resists clean fetching. Do not scrape it. Use:

1. **Assessor Data Download** — `https://info.kingcounty.gov/assessor/datadownload/default.aspx`
   Bulk extracts (the certified roll the Assessor itself uses). Relevant tables:
   - `rpacct_extr` — Real Property Account: assessed + taxable values, land/improvement split, levy
     code. Keyed by account (Major+Minor; up to 3 accounts per parcel).
   - `parcel_extr` — Parcel Record: one per parcel (Major+Minor), zoning, lot, area attributes.
   - `rpsale_extr` — Real Property Sale: one+ records per sale (Excise Tax No. + Major + Minor).
     **This is the comp engine.** Includes sale price, date, instrument, and warning/exclude codes.
   - Residential Building extract — living area (GLA), year built, grade/condition, bed/bath, etc.
   - Lookup table — decodes coded fields (instrument, warning, grade, condition, area codes).
2. **King County GIS Open Data / ArcGIS REST** — `https://gis-kingcounty.opendata.arcgis.com/`
   Parcel features with address + property info as queryable JSON. Use for address → PIN resolution
   and spatial comp selection (radius / same area). (Note: the legacy permitting parcel-address
   layer is being retired June 1, 2026 — resolve_parcel.py should target the current
   `king-county-real-property` / parcel layer, not the retiring one.)
3. **Treasurer payment portal (billed tax + payment history)** —
   `https://payment.kingcounty.gov/Home/Index?app=PropertyTaxes&Search=<PIN>`
   This page is **JavaScript-rendered** (confirmed: a raw fetch returns only the shell and a
   "Loading…" placeholder — no data). The table is populated by a backend JSON/XHR call. Do NOT
   scrape the page; target the underlying endpoint. This is the source for **actual billed tax per
   year and payment dates**, which the Assessor extracts do not carry — and therefore the source
   for the true per-parcel effective rate (`billed_tax / assessed_value`).

### VERIFIED endpoints and field names (2026-06-23)

1. **Address → PIN (geocoder):**
   `https://gismaps.kingcounty.gov/arcgis/rest/services/Address/KingCo_ParcelAddress_locator/GeocodeServer/findAddressCandidates`
   Params: `SingleLine=<address>&outFields=*&maxLocations=5&f=json`
   PIN in `candidates[].attributes.PIN` (10-char: Major 6 + Minor 4). Score ≥80 = reliable match.

2. **Property info (zoning, lot, use):**
   `https://gismaps.kingcounty.gov/arcgis/rest/services/Property/KingCo_PropertyInfo/MapServer/0/query`
   Params: `where=PIN='<pin>'&outFields=*&f=json`
   Fields: PIN, MAJOR, MINOR, PROPTYPE, KCA_ZONING, KCA_ACRES, PREUSE_CODE, PREUSE_DESC.

3. **Assessed values + building characteristics (per-parcel):**
   `https://blue.kingcounty.com/Assessor/eRealProperty/Dashboard.aspx?ParcelNbr=<PIN>`
   **Server-side rendered** (ASP.NET WebForms) — data is in raw HTML, no JS needed.
   - Tax roll table `id="cphContent_GridViewDBTaxRoll"`: Valued Year, Tax Year, Appraised Land/Imps/Total, Taxable Land/Imps/Total
   - Building details `id="cphContent_DetailsViewPropTypeR"`: Year Built, Total Square Footage, Number Of Bedrooms, Number Of Baths, Grade (N Label), Condition, Lot Size, Views, Waterfront
   - Levy `id="cphContent_FormViewLevyDist_Label1"` (code), `Label2` (year), `LabelRegularRate` ($X.XXXXX per $1,000 AV)

4. **Bulk extracts (for comps):**
   Disclaimer at `https://info.kingcounty.gov/assessor/datadownload/default.aspx` — after checking
   the checkbox, download links appear at `https://aqua.kingcounty.gov/extranet/assessor/<Name>.zip`.
   Filenames: `EXTR_RPSale.csv`, `EXTR_ResBldg.csv`, `EXTR_RPAcct_NoName.csv`.
   Stored in `extracts/` subdirectory; refresh weekly.
   - **rpacct fields:** MAJOR, MINOR, PIN, APPRLANDVAL, APPRIMPSVAL, TAXABLELANDVAL, TAXABLEIMPSVAL, LEVYCODE, BILLYR, TAXSTAT
   - **rpsale fields:** MAJOR, MINOR, EXCISETAXNBR, SALEPRICE, SALEDATE/DOCUMENTDATE, SALEINSTRUMENT (28 codes; 15=Quit Claim), SALEWARNING (space-separated 2-char codes), SALEREASON
   - **resbldg fields:** MAJOR, MINOR, SQFTTOTLIVING, YRBUILT, BLDGGRADE, PCNTCONDITION, BEDROOMS, BATHFULLCOUNT, BATH3QTRCOUNT, BATHHALFCOUNT, STORIES, YRRENOVATED

5. **Treasurer payment portal:** JS-rendered, no accessible XHR endpoint found. **Not needed** —
   the levy rate from eRealProperty (#3) gives the per-parcel effective rate directly:
   `effective_rate = levy_rate_per_1000 / 1000`.

### eSales search (advisory — not used by scripts)

`https://info.kingcounty.gov/assessor/esales/Residential.aspx?ParcelNbr=<PIN>`
The Search POST (with ASP.NET __VIEWSTATE) returns a comp count but the View Sales step requires
JavaScript execution. Usable as a validation check but not as a data source for scripts.

## Levy / effective rate

Preferred: derive the **actual** rate for the subject from its **levy code** rather than a
county-wide average — `effective_rate = total_tax_billed / assessed_value` for the parcel, or the
levy-code millage from the Treasurer/Assessor levy tables. County-wide effective rate runs roughly
0.82%–1.0% and varies materially by city/levy code, so the average is a fallback only.

- [x] VERIFIED: eRealProperty Dashboard provides the per-levy-code rate directly via
      `cphContent_FormViewLevyDist_LabelRegularRate` ($/1000 AV). Year from `Label2`.

## eAppeals petition fields (for petition.json)

The petition requires, at minimum:
- Filer identity: owner name, mailing address, daytime phone, and signature
- Parcel / account number(s)
- Property description: address, parcel size, zoning, general building info
- Owner's **opinion of value** (the number being argued for)
- A statement of **specific reasons** the Assessor's value exceeds true and fair market value,
  grounded only in admissible evidence.

- [ ] STILL TODO: exact field list / form (Real Property Petition) and any attachments the portal
      expects, by reviewing the current BOE forms page and eAppeals flow.

## Filing portal & contacts

- eAppeals + petition forms: King County BOE (Board of Appeals & Equalization) site.
- Assessor (informal pre-appeal discussion is allowed and can resolve without a hearing):
  206-296-7300.
- Exemptions worth flagging if the owner may qualify (separate from appeal): senior/disabled (age
  61+, income threshold ~$84k for 2026) and disabled-veteran exemptions — Assessor Exemptions Unit,
  206-296-3920.
