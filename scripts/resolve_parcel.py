#!/usr/bin/env python3
"""Address → PIN via King County ArcGIS ParcelAddress geocoder."""

import json
import sys
import urllib.request
import urllib.parse
import os

GEOCODER_URL = (
    "https://gismaps.kingcounty.gov/arcgis/rest/services"
    "/Address/KingCo_ParcelAddress_locator/GeocodeServer/findAddressCandidates"
)

PROPERTY_INFO_URL = (
    "https://gismaps.kingcounty.gov/arcgis/rest/services"
    "/Property/KingCo_PropertyInfo/MapServer/0/query"
)


def geocode_address(address: str) -> dict:
    params = urllib.parse.urlencode({
        "SingleLine": address,
        "outFields": "*",
        "maxLocations": 5,
        "f": "json",
    })
    url = f"{GEOCODER_URL}?{params}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.loads(resp.read())

    candidates = data.get("candidates", [])
    if not candidates:
        return {"error": "No geocode match", "address": address}

    best = max(candidates, key=lambda c: c.get("score", 0))
    if best.get("score", 0) < 80:
        return {"error": f"Low confidence match (score={best['score']})", "address": address}

    attrs = best.get("attributes", {})
    pin = attrs.get("PIN", "")
    if not pin or len(pin) != 10:
        return {"error": f"No valid PIN returned (got '{pin}')", "address": address}

    return {
        "pin": pin,
        "major": pin[:6],
        "minor": pin[6:],
        "matched_address": attrs.get("Match_addr", ""),
        "score": best["score"],
        "location": best.get("location", {}),
    }


def get_property_info(pin: str) -> dict:
    """Fetch area code, zoning, lot acres, present use from PropertyInfo layer."""
    params = urllib.parse.urlencode({
        "where": f"PIN='{pin}'",
        "outFields": "*",
        "f": "json",
    })
    url = f"{PROPERTY_INFO_URL}?{params}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.loads(resp.read())

    features = data.get("features", [])
    if not features:
        return {}

    attrs = features[0].get("attributes", {})
    return {
        "prop_type": attrs.get("PROPTYPE"),
        "zoning": attrs.get("KCA_ZONING"),
        "lot_acres": attrs.get("KCA_ACRES"),
        "present_use_code": attrs.get("PREUSE_CODE"),
        "present_use_desc": (attrs.get("PREUSE_DESC") or "").strip(),
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: resolve_parcel.py <address> [run_dir]", file=sys.stderr)
        sys.exit(1)

    address = sys.argv[1]
    run_dir = sys.argv[2] if len(sys.argv) > 2 else "."

    result = geocode_address(address)
    if "error" in result:
        print(json.dumps(result, indent=2))
        sys.exit(1)

    info = get_property_info(result["pin"])
    result["property_info"] = info

    os.makedirs(run_dir, exist_ok=True)
    out_path = os.path.join(run_dir, "parcel.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Resolved: {result['matched_address']}")
    print(f"PIN: {result['pin']} (Major={result['major']}, Minor={result['minor']})")
    if info:
        print(f"Zoning: {info.get('zoning')}, Use: {info.get('present_use_desc')}, Lot: {info.get('lot_acres')} acres")
    print(f"Written to {out_path}")


if __name__ == "__main__":
    main()
