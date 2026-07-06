#!/usr/bin/env python3
"""PIN → assessed value, characteristics, and levy rate from KC eRealProperty."""

import json
import os
import re
import sys
import urllib.request

EREALP_URL = "https://blue.kingcounty.com/Assessor/eRealProperty/Dashboard.aspx"


def fetch_page(pin: str) -> str:
    url = f"{EREALP_URL}?ParcelNbr={pin}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (property-tax-appeal-forge)",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_building_details(html: str) -> dict:
    """Parse the DetailsViewPropTypeR table (label/value pairs in <td> cells)."""
    match = re.search(
        r'id="cphContent_DetailsViewPropTypeR"(.*?)</table>', html, re.DOTALL
    )
    if not match:
        return {}

    table = match.group(1)
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.DOTALL)
    details = {}
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) >= 2:
            label = re.sub(r"<[^>]+>", "", cells[0]).strip()
            value = re.sub(r"<[^>]+>", "", cells[1]).strip()
            if label:
                details[label] = value

    result = {}

    sqft = details.get("Total Square Footage", "")
    if sqft.replace(",", "").isdigit():
        result["living_area_sqft"] = int(sqft.replace(",", ""))

    yr = details.get("Year Built", "")
    if yr.isdigit():
        result["year_built"] = int(yr)

    beds = details.get("Number Of Bedrooms", "")
    if beds.isdigit():
        result["bedrooms"] = int(beds)

    baths = details.get("Number Of Baths", "")
    try:
        result["bathrooms"] = float(baths)
    except ValueError:
        pass

    grade_raw = details.get("Grade", "")
    grade_m = re.match(r"(\d+)\s*(.*)", grade_raw)
    if grade_m:
        result["grade"] = int(grade_m.group(1))
        result["grade_desc"] = grade_m.group(2).strip()

    result["condition"] = details.get("Condition", "").strip() or None

    lot = details.get("Lot Size", "")
    if lot.replace(",", "").isdigit():
        result["lot_size_sqft"] = int(lot.replace(",", ""))

    views = details.get("Views", "").strip()
    if views:
        result["views"] = views.lower() != "no"

    waterfront = details.get("Waterfront", "").strip()
    if waterfront:
        result["waterfront"] = waterfront.lower() != "no"

    return result


def parse_tax_roll(html: str) -> dict:
    """Parse the GridViewDBTaxRoll table — most recent row is current assessment."""
    match = re.search(
        r'id="cphContent_GridViewDBTaxRoll"(.*?)</table>', html, re.DOTALL
    )
    if not match:
        return {}

    table = match.group(1)

    headers = re.findall(r"<th[^>]*>(.*?)</th>", table, re.DOTALL)
    headers = [re.sub(r"<[^>]+>", "", h).strip() for h in headers]

    rows = re.findall(
        r'<tr[^>]*class="[^"]*GridViewRowStyle[^"]*"[^>]*>(.*?)</tr>',
        table,
        re.DOTALL,
    )
    if not rows:
        return {}

    cells = re.findall(r"<td[^>]*>(.*?)</td>", rows[0], re.DOTALL)
    cells = [re.sub(r"<[^>]+>", "", c).strip().replace(",", "") for c in cells]

    def safe_int(s):
        try:
            return int(s)
        except ValueError:
            return None

    h_map = {h: i for i, h in enumerate(headers)}

    def get(key):
        return safe_int(cells[h_map[key]]) if key in h_map and h_map[key] < len(cells) else None

    return {
        "assessment_year": get("Valued Year"),
        "tax_year": get("Tax Year"),
        "land_value": get("Appraised Land Value ($)"),
        "improvement_value": get("Appraised Imps Value ($)"),
        "total_assessed_value": get("Appraised Total ($)"),
        "taxable_land_value": get("Taxable Land Value ($)"),
        "taxable_improvement_value": get("Taxable Imps Value ($)"),
        "taxable_total": get("Taxable Total ($)"),
    }


def parse_levy(html: str) -> dict:
    """Parse levy code, year, and rate from the FormViewLevyDist section."""
    result = {}
    patterns = {
        "levy_code": r'id="cphContent_FormViewLevyDist_Label1"[^>]*>(\d+)<',
        "levy_year": r'id="cphContent_FormViewLevyDist_Label2"[^>]*>(\d+)<',
        "levy_rate_per_1000": r'id="cphContent_FormViewLevyDist_LabelRegularRate"[^>]*>\$?([\d.]+)<',
    }
    for key, pat in patterns.items():
        m = re.search(pat, html)
        if m:
            val = m.group(1)
            if key == "levy_rate_per_1000":
                result[key] = float(val)
            else:
                result[key] = val if key == "levy_code" else int(val)

    if "levy_rate_per_1000" in result:
        result["effective_rate"] = round(result["levy_rate_per_1000"] / 1000.0, 8)

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: fetch_account_value.py <PIN> [run_dir]", file=sys.stderr)
        sys.exit(1)

    pin = sys.argv[1]
    run_dir = sys.argv[2] if len(sys.argv) > 2 else "."

    html = fetch_page(pin)

    characteristics = parse_building_details(html)
    assessed = parse_tax_roll(html)
    levy = parse_levy(html)

    subject = {
        "parcel": {"pin": pin, "jurisdiction": "king-county-wa"},
        "assessed": {**assessed, "levy_code": levy.get("levy_code"), "_source": "eRealProperty"},
        "characteristics": {**characteristics, "_source": "eRealProperty"},
        "effective_rate": {
            "value": levy.get("effective_rate"),
            "levy_rate_per_1000": levy.get("levy_rate_per_1000"),
            "levy_code": levy.get("levy_code"),
            "_source": "eRealProperty levy distribution",
        },
    }

    os.makedirs(run_dir, exist_ok=True)
    out_path = os.path.join(run_dir, "subject.json")

    if os.path.exists(out_path):
        with open(out_path) as f:
            existing = json.load(f)
        existing["assessed"] = subject["assessed"]
        existing["characteristics"] = subject["characteristics"]
        existing["effective_rate"] = subject["effective_rate"]
        subject = existing

    with open(out_path, "w") as f:
        json.dump(subject, f, indent=2)

    av = assessed.get("total_assessed_value")
    yr = assessed.get("tax_year")
    sqft = characteristics.get("living_area_sqft")
    rate = levy.get("effective_rate")
    print(f"PIN {pin} — Tax Year {yr}")
    print(f"Assessed: ${av:,}" if av else "Assessed: unknown")
    print(f"  Land: ${assessed.get('land_value', 0):,}  Impr: ${assessed.get('improvement_value', 0):,}")
    print(f"  {sqft} sqft, {characteristics.get('year_built')} built, grade {characteristics.get('grade')} ({characteristics.get('grade_desc')})")
    print(f"  {characteristics.get('bedrooms')} bed / {characteristics.get('bathrooms')} bath, lot {characteristics.get('lot_size_sqft')} sqft")
    print(f"  Levy code {levy.get('levy_code')}, rate ${levy.get('levy_rate_per_1000')}/1000 (eff {rate:.4%})" if rate else "")
    if av and rate:
        print(f"  Estimated annual tax: ${av * rate:,.0f}")
    print(f"Written to {out_path}")


if __name__ == "__main__":
    main()
