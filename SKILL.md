---
name: king-county-property-tax-appeal
description: >-
  Build a complete, filing-ready property tax assessment appeal package for a King County, WA
  residential property — the same deliverable contingency services (Owlue, Ownwell) charge 25%
  of first-year savings for. Resolves a parcel, pulls the assessed value and comparable sales
  from official King County data, runs a defensible over-assessment analysis, estimates tax
  savings, and generates an evidence packet plus the petition fields needed to file. Use this
  whenever the user wants to appeal, protest, or lower a King County property tax assessment;
  questions whether their assessed value is too high; received a valuation/change-of-value
  notice or a tax-appeal solicitation letter; or asks how much they could save by appealing.
  Trigger even when the user only names a King County property, parcel number, or assessment
  amount and asks "is this worth appealing?"
---

# Property Tax Appeal Forge

Produce a defensible, admissible property tax appeal package from a parcel identifier.

**Scope discipline.** The skill produces only what files a winning petition and what an owner needs
to decide to file: the deadline, the subject's assessed facts, the comparable-sales argument, the
opinion of value, and admissible condition / record-correction evidence. It deliberately excludes
everything that neither submits a petition nor informs that decision — payment-history displays,
tax-trend narratives, contingency-fee comparisons, multi-year projections, and any argument the
board cannot consider. The point is singular: put the owner on the same evidentiary footing as the
assessor, efficiently. When in doubt about whether to add something, ask "does this fact help file
or win the petition?" If not, leave it out.

A tax appeal is a **valuation argument under strict evidence rules**, not a data dump. The whole
skill is built around one constraint: the appeal board can only consider evidence of true and fair
**market value** as of the assessment date — overwhelmingly, comparable **sales**. Encode this or
you generate packets that get dismissed. See "The admissibility rule" below before doing anything.

## When NOT to proceed

Stop and tell the user plainly if any of these is true. A correct "you have no case" or "you've
missed the window" is the right output — never manufacture a case.

- **Deadline passed.** The filing window has closed for this assessment cycle (see Stage 2).
- **No over-assessment.** Your defensible opinion of value comes out at or above the assessed
  value (Stage 5). Appealing risks nothing legally but wastes effort and can occasionally surface
  an *increase* if the assessor cross-appeals; say so.
- **Too few quality comps.** Fewer than 3 genuinely comparable arm's-length sales near the
  assessment date. Without them there is no admissible argument.

## The admissibility rule (read first)

The board considers ONLY market-value evidence. The following are explicitly **inadmissible** and
must never appear as arguments in the packet (King County / WA: WAC 458-14-056(5)):

- "My taxes went up" / the size of the tax increase
- "My neighbor's *assessment* is lower" — assessment-to-assessment comparison is not evidence;
  only **sales** are
- Percentage increase in value year over year
- Personal hardship, ability to pay, or the dollar amount of tax owed

Admissible evidence: comparable sales, a professional appraisal, photographs and contractor bids
documenting condition defects, and corrections to the property record (wrong square footage, bed/
bath count, lot size, or condition).

## Workflow

Work the stages in order. Each writes a structured artifact the next stage reads, so the run is
inspectable and resumable. Default working directory: `./run/<parcel>/`.

### Stage 0 — Load jurisdiction profile

Read `references/jurisdictions/<jurisdiction>.md`. It defines the deadline rule, evidence statute,
data endpoints, filing portal, petition fields, and the levy/effective-rate source. **Everything
jurisdiction-specific lives there, not in this file.** v1 ships `king-county-wa.md`. If the
property is outside a shipped jurisdiction, tell the user the data layer isn't built for it yet and
offer to do a manual-input run (user supplies AV, comps, and deadline).

### Stage 1 — Intake & parcel resolution

Resolve the property to a canonical record. Run `scripts/resolve_parcel.py` (address → PIN via the
jurisdiction's parcel service) then `scripts/fetch_account_value.py` (current assessed value, land/
improvement split, tax year, levy code, and characteristics from the account + parcel + residential-
building extracts). The address resolves nearly everything; the owner supplies only what public data
cannot — which is also exactly where the owner out-informs the mass-appraisal model.

Collect from the **owner**:

*Required to file*
1. **Filer identity** — name, mailing address, daytime phone, signature authority. Administrative,
   but the petition cannot be submitted without it; feeds `petition.json`.
2. **Deadline confirmation** — the mailing date printed on the change-of-value notice (the
   authoritative trigger). Auto-derive the due date from the portal where possible, but have the
   owner confirm it against the actual notice — missing it is fatal and unrecoverable for the cycle.

*The owner's evidentiary edge (the heart of the case — request all that apply)*
3. **Condition defects** — deferred maintenance, damage, dated systems, functional problems; anything
   that would make the property sell below a clean comp. The model assumes average condition, so this
   is usually the single biggest lever.
4. **Record corrections** — surface the fetched characteristics and ask the owner to flag errors
   (living area, bed/bath, lot size, grade). A wrong square footage is an admissible, often decisive
   correction the assessor's model will not catch on its own.
5. **Recent purchase** — price and date, if bought near the assessment date. An arm's-length purchase
   below the assessed value is frequently the strongest single piece of market-value evidence.

*Optional exhibits (owner-supplied files, high value when present)*
6. Photos of defects, contractor repair bids, and any recent independent appraisal.

Write `subject.json`.

### Stage 2 — Deadline gate

Compute the filing deadline from the jurisdiction rule and the mailing date. If it has passed,
**stop** and tell the user when the next cycle opens. Otherwise record the deadline and the
evidence-exchange rule in `deadline.md`. Never invent an exact date when the notice mailing date
or hearing date is unknown.

### Stage 3 — Comp acquisition

Pull candidate comparable **sales** from the jurisdiction's sales extract via `scripts/fetch_comps.py`.
Filter to defensible comps:

- **Time:** sales bracketing the assessment date (Jan 1 of the assessment year). Closer is better;
  apply a market-time adjustment in Stage 4 rather than discarding, but prefer ±12 months.
- **Geography:** same neighborhood/area code first, then widen only as needed.
- **Physical similarity:** living area within ~±20%, comparable year built, same property type and
  structure grade/quality.
- **Arm's-length only:** exclude non-arm's-length transfers (intra-family, estate, foreclosure,
  partial-interest, corrected/forfeited) using the sale instrument and warning codes. The
  jurisdiction profile lists the exclude codes.

Aim to retain 5–8 candidates so 3–5 survive adjustment.

**Advocacy posture.** This is the owner's case, not a neutral appraisal — among genuinely
comparable, arm's-length sales, preferentially select and lead with those supporting a *lower*
value. That is the legitimate purpose of the petition. Two limits keep it winning rather than
losing:

1. Every retained comp must be genuinely comparable and arm's-length. Cherry-picking unrepresentative
   sales is transparent to the assessor and discredits the entire packet, not just the bad comp.
2. Do not suppress a sale that is *clearly more comparable* than your chosen comps merely because it
   sold high. The assessor will raise it. Retain it, flag it as the **likely opposing comp**, and
   distinguish it in Stage 4 (condition, features, timing) so the packet pre-empts the rebuttal
   instead of getting ambushed by it.

Write `comps.json` (retained comps plus any flagged opposing comp).

### Stage 4 — Adjustment & valuation

Adjust each comp to the subject with a transparent grid (`scripts/adjust_and_value.py`):
time/market, living area (GLA), lot size, grade/condition, bed/bath, and notable features (garage,
view, waterfront). Adjustments must be defensible and documented — the grid IS the argument.

Derive an indicated value range, then choose a **conservative opinion of value** (lean toward the
better-supported low end; you are arguing the assessor is high, but an aggressive number invites
rebuttal). If Stage 3 flagged a likely opposing comp, run it through the same grid and write a short
**distinguishing note** — the specific, documented reasons it overstates the subject's value
(superior condition, larger GLA, a view the subject lacks, a sale date further from Jan 1). Write
`valuation.json` with the grid, the range, the opinion, the rationale, and any distinguishing note.

### Stage 5 — Case test (go / no-go)

`scripts/case_test.py`: compute the over-assessment delta and decide whether filing is worth it —
the owner's core decision. Use the **actual per-parcel effective rate** (billed tax ÷ assessed
value, from the Treasurer endpoint in the jurisdiction profile), not a county-wide average, so the
number is real.

- `delta = assessed_value − opinion_of_value`. If `delta <= 0`, trigger the "no over-assessment"
  stop from "When NOT to proceed" — report no case honestly.
- `estimated_reduction = delta × effective_rate`, reported as a single decision-support figure: just
  enough to tell the owner whether the petition is worth their time.

Write the decision and the two numbers into the run summary. No separate savings document, no
multi-year or fee-comparison framing — those don't file a petition.

### Stage 6 — Admissibility QA

Before building the packet, verify:

- No inadmissible argument (tax delta, assessment comparison, hardship) appears anywhere.
- ≥3 retained comps, each arm's-length, each with a documented adjustment line.
- The opinion of value is supported by the comp range, not asserted.
- **Defensibility:** no sale clearly more comparable than the retained set was excluded; if one
  exists, it is retained and distinguished, not hidden. Adjustments are applied consistently across
  comps (no direction reversed to manufacture the result). The packet survives an adverse read.
- Any property-record corrections cite the specific field and the correct value.

Fix or remove anything that fails. This stage is a gate, not a formality.

### Stage 7 — Packet build

`scripts/build_packet.py` (delegates rendering to the `pdf` skill). Produce exactly two filing
artifacts plus the deadline — nothing else:

- **`petition.json`** — the jurisdiction's petition fields pre-filled (parcel, owner's opinion of
  value, the required statement of reasons grounded only in market value), ready to transcribe into
  the online portal or a fillable form. This is the thing that files the appeal.
- **`evidence_packet.pdf`** — cover page stating the opinion of value and the single sentence of why
  the assessor's value is wrong; comparable-sales grid with adjustments; a location map of subject +
  comps; the adjustment methodology; condition exhibits (photos/bids) if provided. This is the thing
  that wins it.
- **`deadline.md`** — the filing deadline and evidence-exchange rule, with exact dates only when
  the controlling notice dates are known, surfaced in the summary.

Close by telling the owner the filing deadline, where to file, and that they must still pay the
existing tax bill while the appeal is pending to avoid penalties (a refund issues if they win).

## Scripts

| Script | Purpose |
|---|---|
| `scripts/resolve_parcel.py` | Address → PIN via the jurisdiction parcel service |
| `scripts/fetch_account_value.py` | Assessed value, splits, characteristics from extracts |
| `scripts/fetch_comps.py` | Candidate comparable sales from the sales extract |
| `scripts/adjust_and_value.py` | Adjustment grid → indicated range → opinion of value |
| `scripts/case_test.py` | Over-assessment delta + real per-parcel effective rate → go/no-go |
| `scripts/build_packet.py` | Render evidence packet + petition fields |

Each script reads/writes the JSON artifacts above so stages are independently runnable. Endpoints,
field names, and exclude codes are NOT hardcoded in scripts — they are read from the active
jurisdiction profile so a new county is a new reference file plus, at most, a thin data adapter.

## References

- `references/jurisdictions/king-county-wa.md` — KC deadline rule, WAC 458-14 evidence statute,
  data-download + ArcGIS endpoints, extract field maps, sale exclude codes, eAppeals petition
  fields, levy/effective-rate source.
- `references/adjustment-methodology.md` — how to derive and defend each adjustment line.
- `references/disclaimers.md` — required user-facing caveats (not legal/tax advice; estimates are
  ballpark until the actual notice and certified roll are in hand).

## Disclaimers

Surface these to the user, briefly, in the final summary: this is decision-support, not legal or
tax advice; savings figures are estimates until validated against the actual valuation notice and
certified tax roll; the property owner is responsible for the accuracy of everything filed and for
meeting the deadline.
