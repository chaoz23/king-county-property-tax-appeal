#!/usr/bin/env python3
"""Over-assessment delta + effective rate → go/no-go decision (SKILL.md Stage 5)."""

import json
import os
import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: case_test.py <run_dir>", file=sys.stderr)
        sys.exit(1)

    run_dir = sys.argv[1]

    with open(os.path.join(run_dir, "subject.json")) as f:
        subject = json.load(f)
    with open(os.path.join(run_dir, "valuation.json")) as f:
        valuation = json.load(f)

    assessed = subject["assessed"]["total_assessed_value"]
    opinion = valuation["reconciliation"]["opinion_of_value"]
    effective_rate = subject["effective_rate"]["value"]
    levy_rate = subject["effective_rate"].get("levy_rate_per_1000", 0)

    delta = assessed - opinion
    estimated_reduction = round(delta * effective_rate)

    go = delta > 0

    decision = {
        "assessed_value": assessed,
        "opinion_of_value": opinion,
        "delta": delta,
        "delta_pct": round(delta / assessed * 100, 1) if assessed else 0,
        "effective_rate": effective_rate,
        "levy_rate_per_1000": levy_rate,
        "estimated_annual_reduction": estimated_reduction,
        "go": go,
        "comp_count": valuation["reconciliation"]["comp_count"],
    }

    if not go:
        decision["reason"] = (
            "No over-assessment: the defensible opinion of value "
            f"(${opinion:,}) meets or exceeds the assessed value (${assessed:,}). "
            "Filing risks no legal penalty but wastes effort and could invite "
            "an assessor cross-appeal."
        )
    else:
        decision["reason"] = (
            f"Over-assessment of ${delta:,} ({decision['delta_pct']}%). "
            f"Estimated first-year tax reduction: ${estimated_reduction:,}. "
            f"Based on {decision['comp_count']} adjusted comparable sales."
        )

    out_path = os.path.join(run_dir, "decision.json")
    with open(out_path, "w") as f:
        json.dump(decision, f, indent=2)

    print(f"{'GO' if go else 'NO-GO'} — Case test for PIN {subject['parcel']['pin']}")
    print(f"  Assessed value:     ${assessed:,}")
    print(f"  Opinion of value:   ${opinion:,}")
    print(f"  Delta:              ${delta:,} ({decision['delta_pct']}%)")
    print(f"  Effective rate:     {effective_rate:.4%} (${levy_rate}/1000)")
    print(f"  Est. annual saving: ${estimated_reduction:,}")
    if go:
        print(f"\n  Worth filing. Estimated first-year savings: ${estimated_reduction:,}")
    else:
        print(f"\n  Not worth filing. No over-assessment found.")
    print(f"\nWritten to {out_path}")


if __name__ == "__main__":
    main()
