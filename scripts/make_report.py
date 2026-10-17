"""Render reports/results.json (from evaluate.py --out) as a markdown table of ward accuracy."""
import json
import sys
from decimal import ROUND_HALF_UP, Decimal

r = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "reports/results.json"))
sets = ["test", "test_hard", "dev_real", "dev2_real", "final_real"]
systems = ["baseline", "rules", "model", "oracle"]
names = {"baseline": "vietnamadminunits (rule-based library)", "rules": "Rule-based splitter + resolver",
         "model": "**XLM-R + resolver**", "oracle": "Gold spans + resolver (upper bound)"}


def pct(x):
    return str(Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


print("| System | " + " | ".join(sets) + " | ms/addr |")
print("|---|" + "---|" * (len(sets) + 1))
for s in systems:
    cells, ms = [], []
    for d in sets:
        v = r.get(f"{d}/{s}")
        cells.append(pct(v["ward_in_candidates"]) if v else "–")
        if v:
            ms.append(v["ms_per_addr"])
    speed = f"{min(ms):.0f}–{max(ms):.0f}" if ms else "–"
    print(f"| {names[s]} | " + " | ".join(cells) + f" | {speed} |")
