"""Build data/gazetteer.json from the MIT-licensed `vietnamadminunits` package data.

Contents:
  old   – 10,040 pre-2025 units (63 provinces, district level, ward level)
  new   – 3,321 post-1/7/2025 units (34 provinces, ward level only)
  province_map / nodiv / div – official old->new mapping (div = old wards split
          across several new wards, with the default target and centroids)
"""
import json
import sqlite3
from pathlib import Path

import vietnamadminunits

ROOT = Path(__file__).resolve().parents[1]
PKG = Path(vietnamadminunits.__file__).parent / "data"


def kw(value):
    return json.loads(value) if value else []


def main():
    db = sqlite3.connect(PKG / "dataset.db")
    db.row_factory = sqlite3.Row

    old = []
    for r in db.execute("select * from admin_units_legacy"):
        old.append({
            "p": r["province"], "pk": r["provinceKey"], "pkw": kw(r["provinceKeywords"]),
            "d": r["district"], "dk": r["districtKey"], "dtype": r["districtType"], "dkw": kw(r["districtKeywords"]),
            "w": r["ward"], "wk": r["wardKey"], "wtype": r["wardType"], "wkw": kw(r["wardKeywords"]),
            "lat": r["wardLat"] or r["districtLat"], "lon": r["wardLon"] or r["districtLon"],
        })

    new = []
    for r in db.execute("select * from admin_units"):
        new.append({
            "p": r["province"], "pk": r["provinceKey"], "pkw": kw(r["provinceKeywords"]),
            "w": r["ward"], "wk": r["wardKey"], "wtype": r["wardType"], "wkw": kw(r["wardKeywords"]),
            "lat": r["wardLat"], "lon": r["wardLon"],
        })

    conv = json.loads((PKG / "converter_2025.json").read_text())
    out = {
        "source": "vietnamadminunits %s (MIT) – https://github.com/tranngocminhhieu/vietnamadminunits"
                  % getattr(vietnamadminunits, "__version__", "1.0.4"),
        "old": old,
        "new": new,
        "province_map": conv["DICT_PROVINCE"],
        "nodiv": conv["DICT_PROVINCE_WARD_NO_DIVIDED"],
        "div": conv["DICT_PROVINCE_WARD_DIVIDED"],
    }
    dst = ROOT / "data" / "gazetteer.json"
    dst.write_text(json.dumps(out, ensure_ascii=False))
    print(f"old={len(old)} new={len(new)} -> {dst} ({dst.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
