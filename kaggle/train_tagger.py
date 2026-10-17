"""Kaggle GPU job: fine-tune token classifiers for Vietnamese address segmentation.

Self-contained (plain PyTorch loop, no Trainer API so it survives transformers version drift).
Input : /kaggle/input/<dataset>/{train,val,test,test_hard}.jsonl  (tokens + BIO labels)
Output: /kaggle/working/<model_name>/  (fp16 safetensors + tokenizer + metrics.json)
"""
import glob
import json
import math
import os
import random
import time

import numpy as np
import torch
from torch.utils.data import DataLoader
from transformers import AutoModelForTokenClassification, AutoTokenizer, get_linear_schedule_with_warmup

LABELS = ["O", "B-STREET", "I-STREET", "B-WARD", "I-WARD", "B-DISTRICT", "I-DISTRICT", "B-PROVINCE", "I-PROVINCE"]
L2I = {l: i for i, l in enumerate(LABELS)}
MODELS = json.loads(os.environ.get("MODELS", json.dumps([
    ["FacebookAI/xlm-roberta-base", "xlmr-base", 2, 5e-5, 64],
    ["distilbert/distilbert-base-multilingual-cased", "distilmbert", 2, 6e-5, 64],
])))
N_TRAIN = int(os.environ.get("N_TRAIN", "200000"))

DATA = os.environ.get("DATA_DIR") or os.path.dirname(glob.glob("/kaggle/input/**/train.jsonl", recursive=True)[0])
OUT = os.environ.get("OUT_DIR", "/kaggle/working")
dev = "cuda" if torch.cuda.is_available() else "cpu"


def load(name, n=None):
    rows = []
    with open(os.path.join(DATA, name)) as f:
        for i, line in enumerate(f):
            if n and i >= n:
                break
            r = json.loads(line)
            rows.append((r["tokens"], [L2I[x] for x in r["labels"]]))
    return rows


class Collate:
    def __init__(self, tok):
        self.tok = tok

    def __call__(self, batch):
        tok = self.tok
        words = [b[0] or ["."] for b in batch]
        enc = tok(words, is_split_into_words=True, truncation=True, max_length=128, padding=True,
                  return_tensors="pt")
        labels = torch.full(enc["input_ids"].shape, -100, dtype=torch.long)
        for bi, (_, labs) in enumerate(batch):
            prev = None
            for ti, wid in enumerate(enc.word_ids(bi)):
                if wid is not None and wid != prev and wid < len(labs):
                    labels[bi, ti] = labs[wid]
                prev = wid
        enc["labels"] = labels
        return enc


@torch.no_grad()
def evaluate(model, loader):
    model.eval()
    tok_ok = tok_n = seq_ok = seq_n = 0
    for batch in loader:
        batch = {k: v.to(dev) for k, v in batch.items()}
        with torch.autocast("cuda", dtype=torch.float16, enabled=dev == "cuda"):
            logits = model(**{k: v for k, v in batch.items() if k != "labels"}).logits
        pred = logits.argmax(-1)
        mask = batch["labels"] != -100
        eq = (pred == batch["labels"]) | ~mask
        tok_ok += ((pred == batch["labels"]) & mask).sum().item()
        tok_n += mask.sum().item()
        seq_ok += eq.all(-1).sum().item()
        seq_n += eq.shape[0]
    model.train()
    return {"token_acc": tok_ok / tok_n, "sequence_acc": seq_ok / seq_n}


def train_one(hf_name, short, epochs, lr, bs):
    print("data:", DATA, "device:", dev, torch.cuda.get_device_name(0) if dev == "cuda" else "", flush=True)
    random.seed(0); np.random.seed(0); torch.manual_seed(0)
    tok = AutoTokenizer.from_pretrained(hf_name)
    model = AutoModelForTokenClassification.from_pretrained(
        hf_name, num_labels=len(LABELS), id2label=dict(enumerate(LABELS)), label2id=L2I).to(dev)
    train = load("train.jsonl", N_TRAIN)
    collate = Collate(tok)
    tl = DataLoader(train, batch_size=bs, shuffle=True, collate_fn=collate, num_workers=2)
    evals = {n: DataLoader(load(f"{n}.jsonl"), batch_size=128, collate_fn=collate)
             for n in ("val", "test", "test_hard")}
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    total = epochs * len(tl)
    sched = get_linear_schedule_with_warmup(opt, int(0.06 * total), total)
    scaler = torch.cuda.amp.GradScaler(enabled=dev == "cuda")
    step, t0, hist = 0, time.time(), []
    model.train()
    for ep in range(epochs):
        for batch in tl:
            batch = {k: v.to(dev) for k, v in batch.items()}
            with torch.autocast("cuda", dtype=torch.float16, enabled=dev == "cuda"):
                loss = model(**batch).loss
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt); scaler.update(); opt.zero_grad(set_to_none=True); sched.step()
            step += 1
            if step % 200 == 0:
                print(f"[{short}] ep{ep} step {step}/{total} loss {loss.item():.4f} {time.time()-t0:.0f}s", flush=True)
            if step % 2000 == 0 or step == total:
                m = evaluate(model, evals["val"]); m["step"] = step; hist.append(m)
                print(f"[{short}] val {m}", flush=True)
    metrics = {n: evaluate(model, l) for n, l in evals.items()}
    metrics.update({"history": hist, "hf_name": hf_name, "epochs": epochs, "lr": lr, "batch_size": bs,
                    "n_train": len(train), "train_seconds": round(time.time() - t0),
                    "params": sum(p.numel() for p in model.parameters())})
    print(short, json.dumps(metrics), flush=True)
    d = os.path.join(OUT, short)
    model.half()
    for prm in model.parameters():
        prm.data = prm.data.contiguous()
    model.save_pretrained(d, safe_serialization=True)
    tok.save_pretrained(d)
    json.dump(metrics, open(os.path.join(d, "metrics.json"), "w"), indent=2)
    del model; torch.cuda.empty_cache()


if __name__ == "__main__":
    for spec in MODELS:
        train_one(*spec)
    print("DONE")
