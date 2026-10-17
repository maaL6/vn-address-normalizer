"""Generate synthetic train/val/test splits (JSONL)."""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vnaddr.gazetteer import load
from vnaddr.synth import Generator

ap = argparse.ArgumentParser()
ap.add_argument("--train", type=int, default=200_000)
ap.add_argument("--out", default="data/synth")
a = ap.parse_args()
gz = load()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
splits = {  # name: (n, seed, generator kwargs)
    "train": (a.train, 1, {}),
    "val": (5_000, 2, {}),
    "test": (5_000, 3, {}),
    "test_hard": (3_000, 4, {"typo_rate": 0.35, "noaccent_rate": 0.7}),
}
for name, (n, seed, kw) in splits.items():
    g = Generator(gz, seed=seed, **kw)
    with open(out / f"{name}.jsonl", "w") as f:
        for _ in range(n):
            f.write(json.dumps(g.sample(), ensure_ascii=False) + "\n")
    print(name, n)
