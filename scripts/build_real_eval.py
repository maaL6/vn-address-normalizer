"""Turn a list of hand-written addresses into an eval JSONL file.

Input: a JSON list of {"raw", "place", "old_province", "old_district", "old_ward", "street", "confidence"}.
Each gold unit must exist in the gazetteer (names from mergers before 2025 are followed through the
gazetteer keyword lists); rows that cannot be matched are dropped and printed. The new-unit gold
(province + candidate wards) is attached from the official mapping.

  python scripts/build_real_eval.py written.json data/eval/my_set.jsonl
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vnaddr.gazetteer import load
from vnaddr.text import to_key

src, dst = sys.argv[1], sys.argv[2]
gz = load()
items = json.load(open(src))
if isinstance(items, dict):
    items = items.get("result", items)
PROV_HIST = {"tinhthuathienhue": "thanhphohue"}


def resolve_gold(it):
    """Exact keys first; otherwise follow historic names via the gazetteer keyword lists
    (they include names of units merged before 2025)."""
    pk = to_key(it["old_province"]); pk = PROV_HIST.get(pk, pk)
    dk = to_key(it["old_district"]); wk = to_key(it["old_ward"])
    if pk not in gz.old_prov:
        return None, None, None, False
    dists = gz.old_dist[pk]
    if dk in dists and wk in gz.old_ward.get((pk, dk), {}):
        return pk, dk, wk, False
    cand_d = [d for d, u in dists.items() if d == dk or dk in u.keywords] or list(dists)
    hits = [(d, w) for d in cand_d for w, u in gz.old_ward.get((pk, d), {}).items() if wk == w or wk in u.keywords]
    if len({h for h in hits}) == 1:
        return pk, hits[0][0], hits[0][1], True
    return None, None, None, False


ok, bad = [], []
for it in items:
    pk, dk, wk, relabel = resolve_gold(it)
    if wk is None:
        bad.append((it["raw"], it["old_province"], it["old_district"], it["old_ward"])); continue
    npk, cands = gz.convert(pk, dk, wk)
    ok.append({"text": it["raw"], "place": it["place"], "fmt": "old", "old": {"pk": pk, "dk": dk, "wk": wk},
               "new_pk": npk, "new_wards": [c[0] for c in cands], "new_default": next(c[0] for c in cands if c[1]),
               "street": it["street"], "relabelled_from_historic_name": relabel, "confidence": it["confidence"], "has_province": True})
seen=set(); uniq=[]
for o in ok:
    if o["text"] not in seen: seen.add(o["text"]); uniq.append(o)
with open(dst, "w") as f:
    for o in uniq: f.write(json.dumps(o, ensure_ascii=False) + "\n")
print(f"kept {len(uniq)} / {len(items)}; rejected {len(bad)} (label not in gazetteer)")
for b in bad[:40]: print("  REJ", b)
