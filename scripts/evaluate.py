"""Evaluate address normalization systems on JSONL eval sets.

Systems:
  oracle   – gold spans (synthetic sets only) -> resolver  : upper bound of the resolver
  rules    – rule-based segmenter -> resolver               : no-ML ablation
  model    – fine-tuned tagger -> resolver                  : our system
  baseline – `vietnamadminunits` convert_address (rule-based open-source library)
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vnaddr.gazetteer import load  # noqa: E402
from vnaddr.resolver import Resolver  # noqa: E402
from vnaddr.tagger import HFTagger, RuleTagger, spans_from_bio  # noqa: E402
from vnaddr.text import tokenize, to_key  # noqa: E402


def load_jsonl(p, limit=None):
    rows = [json.loads(l) for l in open(p)]
    return rows[:limit] if limit else rows


def predict(system, rows, model_dir):
    gz = load()
    res = Resolver(gz)
    t0 = time.perf_counter()
    preds = []
    if system == "oracle":
        for r in rows:
            spans = spans_from_bio(r["text"], tokenize(r["text"]), r["labels"])
            o = res.resolve(spans)
            preds.append(((o.new or {}).get("province_key"), (o.new or {}).get("ward_key"), o.old, o.fmt))
    elif system in ("rules", "model"):
        tagger = RuleTagger() if system == "rules" else HFTagger(model_dir)
        texts = [r["text"] for r in rows]
        if system == "model":
            spans = []
            for i in range(0, len(texts), 64):
                spans += tagger.spans_batch(texts[i:i + 64])
        else:
            spans = [tagger.spans(t) for t in texts]
        for s in spans:
            o = res.resolve(s)
            preds.append(((o.new or {}).get("province_key"), (o.new or {}).get("ward_key"), o.old, o.fmt))
    elif system == "baseline":
        # Offline (no Nominatim geocoding, like our system) and given the gold input format
        # (old vs new) for free, since the library cannot detect it: a favourable setting.
        import vietnamadminunits.converter.converter_2025 as conv
        from vietnamadminunits import ConvertMode, ParseMode, convert_address, parse_address
        conv.get_geo_location = lambda address: None
        for r in rows:
            try:
                if r.get("fmt") == "new":
                    u = parse_address(r["text"], mode=ParseMode.FROM_2025, level=2)
                else:
                    u = convert_address(r["text"], mode=ConvertMode.CONVERT_2025)
                preds.append((u.province_key, u.ward_key, None, None))
            except Exception:
                preds.append((None, None, None, None))
    dt = (time.perf_counter() - t0) / max(1, len(rows)) * 1000
    return preds, dt


def score(rows, preds):
    m = defaultdict(lambda: [0, 0])
    for r, (pk, wk, old, fmt) in zip(rows, preds):
        def add(name, ok):
            m[name][0] += int(bool(ok)); m[name][1] += 1
        add("province", pk == r["new_pk"])
        if r["new_wards"]:
            ok = pk == r["new_pk"] and wk in r["new_wards"]
            add("ward_in_candidates", ok)
            add("ward_default", pk == r["new_pk"] and wk == r["new_default"])
            add(f"ward[{r['fmt']}]", ok)
            if len(r["new_wards"]) > 1:
                add("ward[split]", ok)
            if r.get("relabelled_from_historic_name"):
                add("ward[historic_name]", ok)
            if old is not None and r.get("old") and r["old"].get("wk"):
                pass
    return {k: round(100 * a / b, 3) for k, (a, b) in m.items()} | {"n": len(rows)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", nargs="+", default=["data/synth/test.jsonl", "data/synth/test_hard.jsonl",
                                                  "data/eval/dev_real.jsonl", "data/eval/dev2_real.jsonl", "data/eval/final_real.jsonl"])
    ap.add_argument("--systems", nargs="+", default=["oracle", "rules", "model", "baseline"])
    ap.add_argument("--model", default=str(ROOT / "models" / "tagger"))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--errors", default=None,
                    help="[SYSTEM:]DIR - write that system's errors (default: model) to DIR/<set>.jsonl")
    a = ap.parse_args()
    report = {}
    for s in a.sets:
        rows = load_jsonl(s, a.limit)
        for sysname in a.systems:
            if sysname == "oracle" and "labels" not in rows[0]:
                continue
            if sysname == "model" and not (Path(a.model) / "config.json").exists():
                print(f"skipping 'model': no config.json in {a.model}", file=sys.stderr)
                continue
            preds, ms = predict(sysname, rows, a.model)
            sc = score(rows, preds) | {"ms_per_addr": round(ms, 2)}
            report[f"{Path(s).stem}/{sysname}"] = sc
            print(f"{Path(s).stem:12s} {sysname:9s} " + " ".join(f"{k}={v}" for k, v in sc.items()), flush=True)
            err_sys, _, err_path = a.errors.rpartition(":") if a.errors else ("", "", "")
            err_sys = err_sys or "model"
            if a.errors and sysname == err_sys:
                Path(err_path).mkdir(parents=True, exist_ok=True)
                with open(Path(err_path) / f"{Path(s).stem}.jsonl", "w") as f:
                    for r, p in zip(rows, preds):
                        if not r["new_wards"] or (p[0] == r["new_pk"] and p[1] in r["new_wards"]):
                            continue
                        f.write(json.dumps({"text": r["text"], "gold": [r["new_pk"], r["new_wards"], r.get("old")],
                                            "pred": [p[0], p[1], p[2]]}, ensure_ascii=False) + "\n")
    if a.out:
        Path(a.out).write_text(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
