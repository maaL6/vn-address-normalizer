"""CLI.

  python -m vnaddr "12 ng trai p.ben thanh q1 tphcm"          # short summary
  python -m vnaddr --json "12 ng trai p.ben thanh q1 tphcm"   # full result
  python -m vnaddr --csv in.csv --column address --out out.csv
"""
import argparse
import csv
import json
import sys

from .pipeline import Normalizer


def main():
    ap = argparse.ArgumentParser(prog="vnaddr", description="Normalize Vietnamese addresses to the 2025 system")
    ap.add_argument("address", nargs="*", help="address(es) to normalize")
    ap.add_argument("--csv", help="input CSV file")
    ap.add_argument("--column", default="address", help="CSV column holding the address")
    ap.add_argument("--out", help="output CSV (default: stdout)")
    ap.add_argument("--rules", action="store_true", help="use the rule-based splitter instead of the model")
    ap.add_argument("--json", action="store_true", help="print the full result as JSON")
    a = ap.parse_args()
    n = Normalizer(use_model=not a.rules)

    if a.csv:
        with open(a.csv, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, restkey="_extra")
            header = reader.fieldnames or []
            rows = list(reader)
        if a.column not in header:
            sys.exit(f"column '{a.column}' not found; available: {header}")
        texts = [(r.get(a.column) or "").strip() for r in rows]
        results = n.normalize_batch([t or "-" for t in texts])
        extra = [f"vnaddr_{c}" for c in ("new_address", "new_ward", "new_province", "old_ward", "old_district",
                                          "old_province", "split_ward", "confidence")]
        out = open(a.out, "w", newline="", encoding="utf-8") if a.out else sys.stdout
        w = csv.DictWriter(out, fieldnames=header + extra, extrasaction="ignore")
        w.writeheader()
        for r, t, res in zip(rows, texts, results):
            new, old = (res.get("new") or {}) if t else {}, (res.get("old") or {}) if t else {}
            vals = [new.get("full_address"), new.get("ward"), new.get("province"), old.get("ward"),
                    old.get("district"), old.get("province"), res["split_ward"] if t else False,
                    res["confidence"] if t else 0.0]
            w.writerow({k: r.get(k) for k in header} | dict(zip(extra, vals)))
        if a.out:
            out.close()
        return
    if not a.address:
        ap.error("give an address or --csv")
    for text in a.address:
        res = n.normalize(text)
        if a.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            print(summary(res))


def summary(res: dict) -> str:
    old, new = res.get("old"), res.get("new")
    if not new:
        return "could not resolve this address"
    lines = []
    if old:
        lines.append("old: " + ", ".join(x for x in (old.get("ward"), old.get("district"), old.get("province")) if x))
    lines.append("new: " + new["full_address"])
    if res.get("split_ward"):
        lines.append("     (old ward was split; also possible: "
                     + ", ".join(a["ward"] for a in res["alternatives"] if not a["default"]) + ")")
    lines.append(f"confidence: {res['confidence']}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
