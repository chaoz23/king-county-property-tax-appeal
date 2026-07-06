#!/usr/bin/env python3
"""Candidate comparable sales from KC Assessor extracts (rpsale + resbldg).

Reads locally-cached EXTR_RPSale.csv and EXTR_ResBldg.csv, filters per
SKILL.md Stage 3 (time / geography / physical / arm's-length), and writes
comps.json. Run download_extracts.sh first if extracts are missing.
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from datetime import datetime, timedelta

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACTS_DIR = os.path.join(SKILL_DIR, "extracts")

# King County non-arm's-length sale warning codes (exclude from comps)
EXCLUDE_WARNINGS = {
    "1",   # Partial interest transfer
    "2",   # Related party / intra-family
    "3",   # Estate / inheritance
    "4",   # Foreclosure / bank sale
    "5",   # Court ordered
    "6",   # Government / tax exempt
    "7",   # Corrected sale
    "8",   # Forfeiture
    "9",   # Non-representative (e.g. trade, gift)
    "11",  # Questionable title
    "12",  # Bankruptcy
    "18",  # Property with personal property
    "19",  # Undisclosed terms
    "21",  # Below market (short sale, etc.)
    "25",  # Assemblage
    "26",  # Lease interest
    "31",  # Related party (confirmed)
    "32",  # Quit claim (non-arm's-length indicator)
    "41",  # Previously foreclosed
    "50",  # Unverified
    "51",  # Non-market condition
    "59",  # Other non-arm's-length
    "66",  # Nominal price
}

# Instrument codes that signal non-arm's-length transfers
EXCLUDE_INSTRUMENTS = {
    "15",  # Quit Claim Deed
    "26",  # Personal Representative Deed (estate)
}


def parse_optional_int(row: dict, *keys: str) -> int | None:
    """Parse the first populated integer field, preserving missing as None."""
    for key in keys:
        raw = row.get(key)
        if raw is None or str(raw).strip() == "":
            continue
        try:
            return int(str(raw).strip())
        except ValueError:
            continue
    return None


def parse_optional_float(row: dict, *keys: str) -> float | None:
    """Parse the first populated float field, preserving missing as None."""
    for key in keys:
        raw = row.get(key)
        if raw is None or str(raw).strip() == "":
            continue
        try:
            return float(str(raw).strip())
        except ValueError:
            continue
    return None


def load_resbldg(extracts_dir: str) -> dict:
    """Load residential building extract → dict keyed by PIN."""
    path = os.path.join(extracts_dir, "EXTR_ResBldg.csv")
    if not os.path.exists(path):
        return {}

    buildings = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            major = (row.get("Major") or row.get("MAJOR") or "").strip().zfill(6)
            minor = (row.get("Minor") or row.get("MINOR") or "").strip().zfill(4)
            pin = major + minor

            sqft = parse_optional_int(row, "SqFtTotLiving", "SQFTTOTLIVING")
            yr = parse_optional_int(row, "YrBuilt", "YRBUILT")
            grade = parse_optional_int(row, "BldgGrade", "BLDGGRADE")
            beds = parse_optional_int(row, "Bedrooms", "BEDROOMS")

            baths_full = parse_optional_int(row, "BathFullCount", "BATHFULLCOUNT")
            baths_3q = parse_optional_int(row, "Bath3qtrCount", "BATH3QTRCOUNT")
            baths_half = parse_optional_int(row, "BathHalfCount", "BATHHALFCOUNT")
            bath_parts = (baths_full, baths_3q, baths_half)
            bath_count = None
            if any(part is not None for part in bath_parts):
                bath_count = (
                    (baths_full or 0)
                    + 0.75 * (baths_3q or 0)
                    + 0.5 * (baths_half or 0)
                )

            condition = parse_optional_int(row, "PcntCondition", "PCNTCONDITION")
            stories = parse_optional_float(row, "Stories", "STORIES")

            zipcode = (row.get("ZipCode") or "").strip()[:5]

            buildings[pin] = {
                "sqft": sqft,
                "year_built": yr,
                "grade": grade,
                "bedrooms": beds,
                "bathrooms": bath_count,
                "condition_pct": condition,
                "stories": stories,
                "zipcode": zipcode,
            }

    return buildings


def parse_sale_date(raw: str) -> datetime | None:
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%m/%d/%Y", "%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def is_arms_length(warning_str: str, instrument: str) -> bool:
    """Return True if the sale appears arm's-length (no exclude flags)."""
    if instrument.strip() in EXCLUDE_INSTRUMENTS:
        return False
    warnings = warning_str.strip().split()
    return not any(w in EXCLUDE_WARNINGS for w in warnings)


def get_nearby_zips(subject_zip: str) -> set[str]:
    """Return a set of ZIP codes geographically near the subject."""
    renton_area = {"98055", "98056", "98057", "98058", "98059", "98178", "98188"}
    kent_area = {"98030", "98031", "98032", "98042"}
    tukwila_seatac = {"98168", "98188", "98198", "98148"}
    burien_area = {"98146", "98166"}

    zip_clusters = [renton_area, kent_area, tukwila_seatac, burien_area]
    nearby = {subject_zip}
    for cluster in zip_clusters:
        if subject_zip in cluster:
            nearby.update(cluster)
    if len(nearby) == 1:
        nearby.add(subject_zip)
    return nearby


def load_and_filter_sales(
    extracts_dir: str,
    subject: dict,
    buildings: dict,
    assessment_date: datetime,
    subject_zip: str = "",
) -> list[dict]:
    """Load sales extract and filter to comp candidates."""

    path = os.path.join(extracts_dir, "EXTR_RPSale.csv")
    if not os.path.exists(path):
        print(f"ERROR: {path} not found. Run download_extracts.sh first.", file=sys.stderr)
        sys.exit(1)

    subj_sqft = subject["characteristics"].get("living_area_sqft", 0)
    subj_grade = subject["characteristics"].get("grade", 0)
    subj_yr = subject["characteristics"].get("year_built", 0)

    nearby_zips = get_nearby_zips(subject_zip) if subject_zip else set()

    # Time window: ±18 months from assessment date
    date_min = assessment_date - timedelta(days=548)
    date_max = assessment_date + timedelta(days=548)

    candidates = []

    with open(path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            major = (row.get("Major") or row.get("MAJOR") or "").strip().zfill(6)
            minor = (row.get("Minor") or row.get("MINOR") or "").strip().zfill(4)
            pin = major + minor

            # Skip subject property
            if pin == subject["parcel"]["pin"]:
                continue

            # Sale price
            try:
                price = int(float(row.get("SalePrice") or row.get("SALEPRICE") or 0))
            except ValueError:
                continue
            if price < 50000:
                continue

            # Sale date
            sale_date = parse_sale_date(
                row.get("DocumentDate") or row.get("SaleDate") or
                row.get("DOCUMENTDATE") or row.get("SALEDATE") or ""
            )
            if not sale_date or sale_date < date_min or sale_date > date_max:
                continue

            # Arm's-length check
            warning = row.get("SaleWarning") or row.get("SALEWARNING") or ""
            instrument = row.get("SaleInstrument") or row.get("SALEINSTRUMENT") or ""
            if not is_arms_length(warning, instrument):
                continue

            # Get building data
            bldg = buildings.get(pin)
            if not bldg or not bldg["sqft"]:
                continue

            # Physical similarity: sqft within ±30%
            sqft_ratio = bldg["sqft"] / subj_sqft if subj_sqft else 0
            if sqft_ratio < 0.7 or sqft_ratio > 1.3:
                continue

            # Grade within ±2
            if subj_grade:
                if not bldg["grade"]:
                    continue
                if abs(bldg["grade"] - subj_grade) > 2:
                    continue

            # Geographic filter: same or nearby ZIP code
            if nearby_zips and bldg.get("zipcode"):
                if bldg["zipcode"] not in nearby_zips:
                    continue

            comp = {
                "pin": pin,
                "sale_price": price,
                "sale_date": sale_date.strftime("%Y-%m-%d"),
                "instrument": instrument.strip(),
                "warning": warning.strip(),
                "days_from_assessment": (sale_date - assessment_date).days,
                "building": bldg,
                "excise_tax_nbr": (row.get("ExciseTaxNbr") or row.get("EXCISETAXNBR") or "").strip(),
            }

            # Compute similarity score (lower = more comparable)
            sqft_diff = abs(bldg["sqft"] - subj_sqft) / subj_sqft if subj_sqft else 1
            grade_diff = abs(bldg["grade"] - subj_grade) / 13 if subj_grade else 0
            time_diff = abs((sale_date - assessment_date).days) / 365
            yr_diff = abs(bldg["year_built"] - subj_yr) / 50 if subj_yr and bldg["year_built"] else 0
            comp["similarity_score"] = round(sqft_diff + grade_diff + time_diff + yr_diff, 3)

            candidates.append(comp)

    # Sort by similarity (most comparable first), limit to top 15
    candidates.sort(key=lambda c: c["similarity_score"])
    return candidates[:15]


def main():
    if len(sys.argv) < 2:
        print("Usage: fetch_comps.py <run_dir> [extracts_dir]", file=sys.stderr)
        sys.exit(1)

    run_dir = sys.argv[1]
    extracts_dir = sys.argv[2] if len(sys.argv) > 2 else EXTRACTS_DIR

    # Load subject
    subject_path = os.path.join(run_dir, "subject.json")
    if not os.path.exists(subject_path):
        print(f"ERROR: {subject_path} not found. Run fetch_account_value.py first.", file=sys.stderr)
        sys.exit(1)
    with open(subject_path) as f:
        subject = json.load(f)

    # Check extracts exist
    for fname in ["EXTR_RPSale.csv", "EXTR_ResBldg.csv"]:
        fpath = os.path.join(extracts_dir, fname)
        if not os.path.exists(fpath):
            print(f"ERROR: {fpath} not found.", file=sys.stderr)
            print(f"Run: bash scripts/download_extracts.sh", file=sys.stderr)
            sys.exit(1)

    # Assessment date = Jan 1 of assessment year
    assessment_year = subject.get("assessed", {}).get("assessment_year", 2025)
    assessment_date = datetime(assessment_year, 1, 1)

    # Resolve subject ZIP from ResBldg or parcel data
    subj_pin = subject["parcel"]["pin"]
    subject_zip = ""

    print(f"Loading residential building data...")
    buildings = load_resbldg(extracts_dir)
    print(f"  {len(buildings):,} buildings loaded")

    if subj_pin in buildings:
        subject_zip = buildings[subj_pin].get("zipcode", "")
    nearby = get_nearby_zips(subject_zip) if subject_zip else set()
    print(f"  Subject ZIP: {subject_zip}, searching ZIPs: {sorted(nearby) if nearby else 'ALL (no ZIP filter)'}")

    print(f"Searching sales (assessment date: {assessment_date.strftime('%Y-%m-%d')})...")
    candidates = load_and_filter_sales(
        extracts_dir, subject, buildings, assessment_date, subject_zip
    )

    print(f"  {len(candidates)} candidates found")

    # Flag the likely opposing comp (highest price, most comparable)
    if candidates:
        opposing = max(candidates[:8], key=lambda c: c["sale_price"])
        opposing["opposing_comp"] = True

    # Write output
    out = {
        "assessment_date": assessment_date.strftime("%Y-%m-%d"),
        "subject_pin": subject["parcel"]["pin"],
        "subject_sqft": subject["characteristics"].get("living_area_sqft"),
        "subject_grade": subject["characteristics"].get("grade"),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }

    out_path = os.path.join(run_dir, "comps.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"\nTop candidates:")
    for i, c in enumerate(candidates[:8]):
        opp = " [OPPOSING]" if c.get("opposing_comp") else ""
        print(
            f"  {i+1}. PIN {c['pin']} — ${c['sale_price']:,} on {c['sale_date']}"
            f" — {c['building']['sqft']} sqft, grade {c['building']['grade']}"
            f" (score {c['similarity_score']}){opp}"
        )

    print(f"\nWritten to {out_path}")


if __name__ == "__main__":
    main()
