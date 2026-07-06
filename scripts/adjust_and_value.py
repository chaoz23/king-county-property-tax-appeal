#!/usr/bin/env python3
"""Adjustment grid → indicated value range → opinion of value.

Reads comps.json + subject.json. Adjusts each comp to the subject using
market-supported rates, derives an indicated range, and picks a conservative
opinion of value. Writes valuation.json.

See references/adjustment-methodology.md for the adjustment framework.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

# Market-supported adjustment rates for King County residential (2024-2025).
# These are conservative estimates; the grid documents the basis for each.
RATES = {
    "time_monthly_pct": 0.004,    # ~0.4%/mo appreciation (conservative for KC 2024-25)
    "gla_per_sqft": 200,          # marginal $/sqft for average-grade homes
    "lot_per_sqft": 3,            # marginal lot $/sqft (diminishing past ~7500 sqft)
    "grade_per_step": 25000,      # per grade step (e.g. 6→7)
    "bedroom_each": 8000,         # per bedroom difference
    "bathroom_each": 12000,       # per full-bath equivalent difference
    "year_built_per_yr": 400,     # per year of age difference
    "view_premium": 30000,        # view vs no-view
    "waterfront_premium": 150000, # waterfront vs none
}


def require_positive(mapping: dict, key: str, label: str) -> int | float:
    """Return a required positive number or reject incomplete evidence."""
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{label} must be a known positive number")
    return value


def optional_nonnegative(mapping: dict, key: str, label: str) -> int | float | None:
    """Return an optional nonnegative number without converting unknown to zero."""
    value = mapping.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{label} must be a nonnegative number when provided")
    return value


def optional_positive(mapping: dict, key: str, label: str) -> int | float | None:
    """Return an optional positive number without converting unknown to zero."""
    value = mapping.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{label} must be a positive number when provided")
    return value


def adjust_comp(subject: dict, comp: dict, assessment_date: datetime) -> dict:
    """Apply adjustment grid to one comp. Returns adjustment detail dict."""
    subj = subject["characteristics"]
    bldg = comp["building"]
    sale_price = comp["sale_price"]

    adjustments = []

    # 1. Time/market — adjust from sale date to assessment date
    sale_dt = datetime.strptime(comp["sale_date"], "%Y-%m-%d")
    months_diff = (assessment_date - sale_dt).days / 30.44
    time_adj = round(sale_price * RATES["time_monthly_pct"] * months_diff)
    if abs(time_adj) > 0:
        adjustments.append({
            "category": "Time/Market",
            "basis": f"{months_diff:+.1f} months × {RATES['time_monthly_pct']:.1%}/mo",
            "amount": time_adj,
        })

    # 2. Living area (GLA) — comp superior → subtract; comp inferior → add
    subj_sqft = require_positive(subj, "living_area_sqft", "subject living area")
    comp_sqft = require_positive(bldg, "sqft", "comp living area")
    sqft_diff = subj_sqft - comp_sqft  # positive = subject larger = add to comp
    if sqft_diff != 0:
        gla_adj = sqft_diff * RATES["gla_per_sqft"]
        adjustments.append({
            "category": "Living Area (GLA)",
            "basis": f"{sqft_diff:+g} sqft × ${RATES['gla_per_sqft']}/sqft",
            "amount": gla_adj,
        })

    # 3. Lot size (if subject has lot data)
    subj_lot = subj.get("lot_size_sqft", 0)
    # Comps don't have lot size from ResBldg; skip if unavailable
    # TODO: cross-reference with Parcel extract for comp lot sizes

    # 4. Grade
    subj_grade = require_positive(subj, "grade", "subject grade")
    comp_grade = require_positive(bldg, "grade", "comp grade")
    grade_diff = subj_grade - comp_grade
    if grade_diff != 0:
        grade_adj = grade_diff * RATES["grade_per_step"]
        adjustments.append({
            "category": "Grade",
            "basis": f"Subject {subj_grade} vs comp {comp_grade} ({grade_diff:+g} steps × ${RATES['grade_per_step']:,})",
            "amount": grade_adj,
        })

    # 5. Year built (age proxy for condition)
    subj_yr = optional_positive(subj, "year_built", "subject year built")
    comp_yr = optional_positive(bldg, "year_built", "comp year built")
    if subj_yr is not None and comp_yr is not None:
        yr_diff = comp_yr - subj_yr  # positive = comp newer = comp superior = subtract
        if yr_diff != 0:
            age_adj = -yr_diff * RATES["year_built_per_yr"]
            adjustments.append({
                "category": "Year Built / Age",
                "basis": f"Subject {subj_yr} vs comp {comp_yr} ({yr_diff:+g} yrs × ${RATES['year_built_per_yr']})",
                "amount": age_adj,
            })

    # 6. Bedrooms
    subj_beds = optional_nonnegative(subj, "bedrooms", "subject bedrooms")
    comp_beds = optional_nonnegative(bldg, "bedrooms", "comp bedrooms")
    if subj_beds is not None and comp_beds is not None:
        bed_diff = subj_beds - comp_beds
        if bed_diff != 0:
            bed_adj = bed_diff * RATES["bedroom_each"]
            adjustments.append({
                "category": "Bedrooms",
                "basis": f"Subject {subj_beds} vs comp {comp_beds} ({bed_diff:+g} × ${RATES['bedroom_each']:,})",
                "amount": bed_adj,
            })

    # 7. Bathrooms
    subj_baths = optional_nonnegative(subj, "bathrooms", "subject bathrooms")
    comp_baths = optional_nonnegative(bldg, "bathrooms", "comp bathrooms")
    if subj_baths is not None and comp_baths is not None:
        bath_diff = subj_baths - comp_baths
        if abs(bath_diff) >= 0.25:
            bath_adj = round(bath_diff * RATES["bathroom_each"])
            adjustments.append({
                "category": "Bathrooms",
                "basis": f"Subject {subj_baths} vs comp {comp_baths} ({bath_diff:+.2f} × ${RATES['bathroom_each']:,})",
                "amount": bath_adj,
            })

    # 8. View
    subj_view = subj.get("views")
    comp_view = bldg.get("view_utilization")
    # ResBldg ViewUtilization > 0 means view
    if subj_view is not None and comp_view is not None and not subj_view and comp_view:
        adjustments.append({
            "category": "View",
            "basis": "Comp has view, subject does not → subtract",
            "amount": -RATES["view_premium"],
        })

    total_adj = sum(a["amount"] for a in adjustments)
    gross_adj = sum(abs(a["amount"]) for a in adjustments)
    adjusted_price = sale_price + total_adj

    return {
        "pin": comp["pin"],
        "sale_price": sale_price,
        "sale_date": comp["sale_date"],
        "adjustments": adjustments,
        "total_adjustment": total_adj,
        "gross_adjustment": gross_adj,
        "gross_adj_pct": round(gross_adj / sale_price * 100, 1) if sale_price else 0,
        "adjusted_price": adjusted_price,
        "opposing_comp": comp.get("opposing_comp", False),
        "building": bldg,
    }


def reconcile(adjusted_comps: list[dict]) -> dict:
    """Derive indicated range and opinion of value from adjusted comps."""
    if not adjusted_comps:
        raise ValueError("reconciliation requires at least one adjusted comp")

    # The opposing flag identifies a comp to discuss, not evidence to discard.
    # Reconcile every selected comp so the range, weighting, opinion, and count
    # all describe the same evidence set.
    prices = [c["adjusted_price"] for c in adjusted_comps]

    # Weight by inverse gross adjustment percentage (lower = more comparable)
    low = min(prices)
    high = max(prices)

    # Weighted average — weight = 1 / (1 + gross_adj_pct)
    weighted_sum = 0
    weight_total = 0
    for c in adjusted_comps:
        w = 1.0 / (1.0 + c["gross_adj_pct"] / 100.0)
        weighted_sum += c["adjusted_price"] * w
        weight_total += w

    weighted_avg = round(weighted_sum / weight_total) if weight_total else 0

    # Conservative opinion: well-supported low end (below weighted average)
    # Use the average of the lower half of adjusted prices
    sorted_prices = sorted(prices)
    lower_half = sorted_prices[: max(len(sorted_prices) // 2, 2)]
    opinion = round(sum(lower_half) / len(lower_half) / 1000) * 1000  # round to nearest $1K

    return {
        "indicated_range_low": low,
        "indicated_range_high": high,
        "weighted_average": weighted_avg,
        "opinion_of_value": opinion,
        "opinion_basis": (
            f"Average of lower {len(lower_half)} adjusted comps "
            f"(${min(lower_half):,.0f}–${max(lower_half):,.0f}), rounded to nearest $1,000. "
            f"Conservative per advocacy posture: argues assessor is high, "
            f"supported by the comp range."
        ),
        "comp_count": len(adjusted_comps),
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: adjust_and_value.py <run_dir>", file=sys.stderr)
        sys.exit(1)

    run_dir = sys.argv[1]

    with open(os.path.join(run_dir, "subject.json")) as f:
        subject = json.load(f)
    with open(os.path.join(run_dir, "comps.json")) as f:
        comps_data = json.load(f)

    assessment_date = datetime.strptime(comps_data["assessment_date"], "%Y-%m-%d")
    candidates = comps_data["candidates"]

    # Select top 5-8 for the adjustment grid
    selected = candidates[:8]

    print(f"Adjusting {len(selected)} comps to subject (PIN {subject['parcel']['pin']})...\n")

    adjusted = []
    for comp in selected:
        result = adjust_comp(subject, comp, assessment_date)
        adjusted.append(result)

        direction = "↑" if result["total_adjustment"] > 0 else "↓"
        print(
            f"  {result['pin']} — ${result['sale_price']:,} "
            f"{direction} ${abs(result['total_adjustment']):,} "
            f"→ ${result['adjusted_price']:,} "
            f"(gross {result['gross_adj_pct']}%)"
            f"{' [OPPOSING]' if result['opposing_comp'] else ''}"
        )

    reconciliation = reconcile(adjusted)

    # Distinguishing note for opposing comp
    opposing = [c for c in adjusted if c["opposing_comp"]]
    distinguishing_note = None
    if opposing:
        opp = opposing[0]
        reasons = []
        for adj in opp["adjustments"]:
            if adj["amount"] < -5000:
                reasons.append(f"{adj['category']}: {adj['basis']}")
        if reasons:
            distinguishing_note = {
                "opposing_pin": opp["pin"],
                "opposing_sale_price": opp["sale_price"],
                "opposing_adjusted_price": opp["adjusted_price"],
                "reasons_overstates": reasons,
                "summary": (
                    f"Comp {opp['pin']} sold at ${opp['sale_price']:,} but adjusts to "
                    f"${opp['adjusted_price']:,} after accounting for its superior features. "
                    f"It overstates the subject's value because: "
                    + "; ".join(r.split(":")[0] for r in reasons) + "."
                ),
            }

    valuation = {
        "assessment_date": comps_data["assessment_date"],
        "subject_pin": subject["parcel"]["pin"],
        "adjustment_rates": RATES,
        "adjusted_comps": adjusted,
        "reconciliation": reconciliation,
        "distinguishing_note": distinguishing_note,
    }

    out_path = os.path.join(run_dir, "valuation.json")
    with open(out_path, "w") as f:
        json.dump(valuation, f, indent=2)

    ov = reconciliation["opinion_of_value"]
    av = subject["assessed"]["total_assessed_value"]
    print(f"\nIndicated range: ${reconciliation['indicated_range_low']:,} – ${reconciliation['indicated_range_high']:,}")
    print(f"Weighted average: ${reconciliation['weighted_average']:,}")
    print(f"Opinion of value: ${ov:,}")
    print(f"Assessed value:   ${av:,}")
    if ov < av:
        print(f"Over-assessment:  ${av - ov:,} ({(av - ov) / av:.1%})")
    else:
        print(f"No over-assessment (opinion ≥ assessed)")
    if distinguishing_note:
        print(f"\nOpposing comp {distinguishing_note['opposing_pin']}: {distinguishing_note['summary']}")
    print(f"\nWritten to {out_path}")


if __name__ == "__main__":
    main()
