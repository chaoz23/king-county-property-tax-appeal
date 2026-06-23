#!/usr/bin/env python3
"""Build the filing artifacts: petition.json + evidence summary markdown.

Reads all run artifacts (subject, comps, valuation, decision) and produces:
  - petition.json — pre-filled eAppeals petition fields
  - evidence_packet.md — the evidence narrative + adjustment grid (markdown,
    convertible to PDF via the pdf skill or pandoc)
  - deadline.md — filing deadline and evidence-exchange date

SKILL.md Stage 7.
"""

import json
import os
import sys
from datetime import datetime, timedelta


def business_days_before(target: datetime, n: int) -> datetime:
    """Subtract n business days from target."""
    d = target
    while n > 0:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def build_petition(subject: dict, valuation: dict, decision: dict) -> dict:
    """Pre-fill the eAppeals petition fields."""
    recon = valuation["reconciliation"]
    owner = subject.get("owner_inputs", {})

    reasons = (
        f"The Assessor's value of ${decision['assessed_value']:,} exceeds the true and fair "
        f"market value as of January 1, {valuation['assessment_date'][:4]}. "
        f"Analysis of {recon['comp_count']} comparable arm's-length sales in the subject's "
        f"area, adjusted for differences in living area, grade, age, bedrooms, and bathrooms, "
        f"indicates a market value range of "
        f"${recon['indicated_range_low']:,}–${recon['indicated_range_high']:,}. "
        f"The petitioner's opinion of value is ${recon['opinion_of_value']:,}, "
        f"representing the well-supported lower end of the adjusted comparable range."
    )

    return {
        "parcel_number": subject["parcel"]["pin"],
        "property_address": subject["parcel"].get("address", ""),
        "filer_name": owner.get("filer_identity", {}).get("name"),
        "filer_address": owner.get("filer_identity", {}).get("address"),
        "filer_phone": owner.get("filer_identity", {}).get("phone"),
        "opinion_of_value": recon["opinion_of_value"],
        "statement_of_reasons": reasons,
        "assessed_value": decision["assessed_value"],
        "tax_year": subject["assessed"].get("tax_year"),
        "assessment_year": subject["assessed"].get("assessment_year"),
        "_note": "Filer identity fields must be completed before filing.",
    }


def build_evidence_markdown(subject: dict, valuation: dict, decision: dict) -> str:
    """Build the evidence packet as markdown."""
    recon = valuation["reconciliation"]
    subj = subject["characteristics"]
    assessed = subject["assessed"]

    lines = []
    lines.append("# Evidence Packet — Property Tax Assessment Appeal")
    lines.append("")
    lines.append(f"**Parcel:** {subject['parcel']['pin']}")
    lines.append(f"**Address:** {subject['parcel'].get('address', 'N/A')}")
    lines.append(f"**Assessment Year:** {assessed.get('assessment_year')}")
    lines.append(f"**Tax Year:** {assessed.get('tax_year')}")
    lines.append("")
    lines.append("## Opinion of Value")
    lines.append("")
    lines.append(
        f"The petitioner's opinion of the true and fair market value of this property "
        f"as of January 1, {assessed.get('assessment_year')} is "
        f"**${recon['opinion_of_value']:,}**."
    )
    lines.append("")
    lines.append(
        f"The Assessor's value of **${assessed['total_assessed_value']:,}** exceeds market value "
        f"by **${decision['delta']:,}** ({decision['delta_pct']}%), based on analysis of "
        f"{recon['comp_count']} comparable arm's-length sales."
    )
    lines.append("")

    # Subject characteristics
    lines.append("## Subject Property")
    lines.append("")
    lines.append("| Characteristic | Value |")
    lines.append("|---|---|")
    lines.append(f"| Living Area | {subj.get('living_area_sqft', 'N/A'):,} sqft |")
    lines.append(f"| Year Built | {subj.get('year_built', 'N/A')} |")
    lines.append(f"| Grade | {subj.get('grade', 'N/A')} ({subj.get('grade_desc', '')}) |")
    lines.append(f"| Condition | {subj.get('condition', 'N/A')} |")
    lines.append(f"| Bedrooms | {subj.get('bedrooms', 'N/A')} |")
    lines.append(f"| Bathrooms | {subj.get('bathrooms', 'N/A')} |")
    lines.append(f"| Lot Size | {subj.get('lot_size_sqft', 'N/A'):,} sqft |")
    lines.append(f"| Views | {'Yes' if subj.get('views') else 'No'} |")
    lines.append(f"| Waterfront | {'Yes' if subj.get('waterfront') else 'No'} |")
    lines.append(f"| Assessed Land | ${assessed.get('land_value', 0):,} |")
    lines.append(f"| Assessed Improvements | ${assessed.get('improvement_value', 0):,} |")
    lines.append(f"| **Total Assessed** | **${assessed.get('total_assessed_value', 0):,}** |")
    lines.append("")

    # Comparable sales adjustment grid
    lines.append("## Comparable Sales Adjustment Grid")
    lines.append("")

    # Header
    comps = valuation["adjusted_comps"]
    header = "| | " + " | ".join(f"Comp {i+1}" for i in range(len(comps))) + " |"
    sep = "|---|" + "|".join("---:" for _ in comps) + "|"
    lines.append(header)
    lines.append(sep)

    lines.append(
        "| PIN | " + " | ".join(c["pin"] for c in comps) + " |"
    )
    lines.append(
        "| Sale Price | " + " | ".join(f"${c['sale_price']:,}" for c in comps) + " |"
    )
    lines.append(
        "| Sale Date | " + " | ".join(c["sale_date"] for c in comps) + " |"
    )

    # Collect all adjustment categories across all comps
    all_cats = []
    for c in comps:
        for a in c["adjustments"]:
            if a["category"] not in all_cats:
                all_cats.append(a["category"])

    for cat in all_cats:
        vals = []
        for c in comps:
            adj = next((a for a in c["adjustments"] if a["category"] == cat), None)
            if adj:
                amt = adj["amount"]
                vals.append(f"${amt:+,}")
            else:
                vals.append("—")
        lines.append(f"| Adj: {cat} | " + " | ".join(vals) + " |")

    lines.append(
        "| **Total Adjustment** | "
        + " | ".join(f"**${c['total_adjustment']:+,}**" for c in comps)
        + " |"
    )
    lines.append(
        "| **Adjusted Price** | "
        + " | ".join(f"**${c['adjusted_price']:,}**" for c in comps)
        + " |"
    )
    lines.append(
        "| Gross Adj % | "
        + " | ".join(f"{c['gross_adj_pct']}%" for c in comps)
        + " |"
    )
    lines.append("")

    # Reconciliation
    lines.append("## Reconciliation")
    lines.append("")
    lines.append(f"- Indicated range: ${recon['indicated_range_low']:,} – ${recon['indicated_range_high']:,}")
    lines.append(f"- Weighted average (by inverse gross adjustment): ${recon['weighted_average']:,}")
    lines.append(f"- **Opinion of value: ${recon['opinion_of_value']:,}**")
    lines.append(f"- Basis: {recon['opinion_basis']}")
    lines.append("")

    # Distinguishing note for opposing comp
    dn = valuation.get("distinguishing_note")
    if dn:
        lines.append("## Opposing Comp — Distinguishing Note")
        lines.append("")
        lines.append(dn["summary"])
        lines.append("")

    # Adjustment methodology reference
    lines.append("## Adjustment Methodology")
    lines.append("")
    lines.append(
        "Adjustments follow the sales-comparison approach: each comparable sale is "
        "adjusted to reflect what it would have sold for had it been identical to the "
        "subject. A feature where the comp is superior is subtracted; where inferior, "
        "added. Rates are market-supported estimates for King County residential "
        "properties (2024–2025). Lower gross adjustment = more comparable = higher "
        "weight in reconciliation."
    )
    lines.append("")

    rates = valuation["adjustment_rates"]
    lines.append("| Adjustment | Rate | Basis |")
    lines.append("|---|---|---|")
    lines.append(f"| Time/Market | {rates['time_monthly_pct']:.1%}/month | KC residential appreciation |")
    lines.append(f"| Living Area | ${rates['gla_per_sqft']}/sqft | Marginal $/sqft, average grade |")
    lines.append(f"| Grade | ${rates['grade_per_step']:,}/step | Per grade step |")
    lines.append(f"| Year Built | ${rates['year_built_per_yr']}/year | Age/condition proxy |")
    lines.append(f"| Bedrooms | ${rates['bedroom_each']:,}/each | Per bedroom |")
    lines.append(f"| Bathrooms | ${rates['bathroom_each']:,}/each | Per full-bath equivalent |")
    lines.append("")

    return "\n".join(lines)


def build_deadline(subject: dict) -> str:
    """Compute filing deadline from KC rules."""
    assessment_year = subject["assessed"].get("assessment_year", 2025)
    notice_date_str = (subject.get("owner_inputs") or {}).get("notice_mailing_date")

    lines = []
    lines.append("# Filing Deadline")
    lines.append("")

    july1 = datetime(assessment_year, 7, 1)
    if notice_date_str:
        notice_date = datetime.strptime(notice_date_str, "%Y-%m-%d")
        sixty_days = notice_date + timedelta(days=60)
        deadline = max(july1, sixty_days)
        lines.append(f"**Notice mailing date:** {notice_date.strftime('%B %d, %Y')}")
        lines.append(f"**60-day deadline:** {sixty_days.strftime('%B %d, %Y')}")
        lines.append(f"**July 1 deadline:** {july1.strftime('%B %d, %Y')}")
        lines.append(f"**Filing deadline (later of the two):** {deadline.strftime('%B %d, %Y')}")
    else:
        lines.append(f"**July 1 deadline:** {july1.strftime('%B %d, %Y')}")
        lines.append(
            "**Notice mailing date not provided.** The filing deadline is the later of "
            f"July 1, {assessment_year} or 60 days from the notice mailing date. "
            "Confirm the mailing date from the actual valuation notice."
        )
        deadline = july1

    lines.append("")
    evidence_exchange = business_days_before(deadline + timedelta(days=45), 21)
    lines.append(
        f"**Evidence exchange deadline (est.):** {evidence_exchange.strftime('%B %d, %Y')} "
        "(21 business days before estimated hearing)"
    )
    lines.append("")
    lines.append(
        "**File via eAppeals** (King County Board of Appeals & Equalization). "
        "Pay the existing tax bill on schedule while the appeal is pending — "
        "a win yields a corrected bill or refund."
    )
    lines.append("")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: build_packet.py <run_dir>", file=sys.stderr)
        sys.exit(1)

    run_dir = sys.argv[1]

    with open(os.path.join(run_dir, "subject.json")) as f:
        subject = json.load(f)
    with open(os.path.join(run_dir, "valuation.json")) as f:
        valuation = json.load(f)
    with open(os.path.join(run_dir, "decision.json")) as f:
        decision = json.load(f)

    # Merge address from parcel.json if available
    parcel_path = os.path.join(run_dir, "parcel.json")
    if os.path.exists(parcel_path):
        with open(parcel_path) as f:
            parcel = json.load(f)
        if "matched_address" in parcel:
            subject["parcel"]["address"] = parcel["matched_address"]

    if not decision["go"]:
        print("NO-GO: case_test determined no over-assessment. No packet built.")
        sys.exit(0)

    # 1. Petition fields
    petition = build_petition(subject, valuation, decision)
    petition_path = os.path.join(run_dir, "petition.json")
    with open(petition_path, "w") as f:
        json.dump(petition, f, indent=2)
    print(f"Petition fields → {petition_path}")

    # 2. Evidence packet (markdown)
    evidence_md = build_evidence_markdown(subject, valuation, decision)
    evidence_path = os.path.join(run_dir, "evidence_packet.md")
    with open(evidence_path, "w") as f:
        f.write(evidence_md)
    print(f"Evidence packet  → {evidence_path}")

    # 3. Deadline
    deadline_md = build_deadline(subject)
    deadline_path = os.path.join(run_dir, "deadline.md")
    with open(deadline_path, "w") as f:
        f.write(deadline_md)
    print(f"Deadline         → {deadline_path}")

    # Summary
    ov = valuation["reconciliation"]["opinion_of_value"]
    av = decision["assessed_value"]
    saving = decision["estimated_annual_reduction"]
    print(f"\n{'='*60}")
    print(f"APPEAL PACKET READY")
    print(f"  Assessed:        ${av:,}")
    print(f"  Opinion:         ${ov:,}")
    print(f"  Over-assessment: ${av - ov:,}")
    print(f"  Est. tax saving: ${saving:,}/year")
    print(f"{'='*60}")
    print(f"\nNext steps:")
    print(f"  1. Confirm the notice mailing date (deadline depends on it)")
    print(f"  2. Fill in filer identity in petition.json")
    print(f"  3. Review evidence_packet.md and add condition photos/bids if available")
    print(f"  4. File via eAppeals before the deadline")
    print(f"  5. Pay the existing tax bill on schedule")


if __name__ == "__main__":
    main()
