"""Compare fp32 vs dynamic-int8 tagger on CPU: speed and tag sequence accuracy.

  python scripts/int8_check.py [models/tagger] [data/synth/test_hard.jsonl] > reports/int8_check.md
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vnaddr.tagger import HFTagger  # noqa: E402

model = sys.argv[1] if len(sys.argv) > 1 else "models/tagger"
data = sys.argv[2] if len(sys.argv) > 2 else "data/synth/test_hard.jsonl"
rows = [json.loads(l) for l in open(data)][:512]
texts = [r["text"] for r in rows]
res = {}
for q in (False, True):
    t = HFTagger(model, quantize=q)
    t.predict_batch(texts[:8])  # warm-up
    t0 = time.perf_counter()
    out = []
    for i in range(0, len(texts), 64):
        out += t.predict_batch(texts[i:i + 64])
    batch_ms = (time.perf_counter() - t0) / len(texts) * 1000
    t0 = time.perf_counter()
    for x in texts[:100]:
        t.predict_batch([x])
    single_ms = (time.perf_counter() - t0) / 100 * 1000
    acc = sum(r["labels"] == l for r, (_, l) in zip(rows, out)) / len(rows)
    res["int8" if q else "fp32"] = (batch_ms, single_ms, acc)

print(f"# fp32 vs dynamic int8 ({Path(model).resolve().name}, {len(rows)} addresses from {Path(data).name}, CPU)\n")
print("| | ms/address (batch 64) | ms/address (one at a time) | tag sequence accuracy |")
print("|---|---|---|---|")
for k, (b, s, a) in res.items():
    print(f"| {k} | {b:.1f} | {s:.1f} | {100 * a:.1f}% |")
