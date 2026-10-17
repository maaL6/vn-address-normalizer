"""Address segmenters: a rule-based one (ablation / no-model fallback) and a fine-tuned
transformer token classifier."""
import os
import re
from pathlib import Path

from .text import nfc, strip_accents, tokenize

ROLES = ("STREET", "WARD", "DISTRICT", "PROVINCE")
NOISE_PREFIX = re.compile(r"^\s*(địa chỉ( giao hàng)?|đc|đ/c|add|address|giao tới)\s*:?\s*", re.I)
NOISE_SUFFIX = re.compile(r"[\s,]*(việt nam|viet nam|vietnam|vn)?[\s,]*(\d{5,6})?\s*$", re.I)


def spans_from_bio(text, toks, labels):
    """Merge BIO labels into {role: span_text}; multiple STREET pieces are joined with ', '."""
    spans, cur, cur_role = {}, None, None
    pieces = []
    for (tok, s, e), lab in zip(toks, labels):
        role = lab[2:] if lab != "O" else None
        if role and (lab.startswith("B-") or role != cur_role):
            if cur:
                pieces.append((cur_role, cur))
            cur, cur_role = [s, e], role
        elif role:
            cur[1] = e
        else:
            if cur:
                pieces.append((cur_role, cur))
            cur, cur_role = None, None
    if cur:
        pieces.append((cur_role, cur))
    for role, (s, e) in pieces:
        t = text[s:e].strip(" ,.-")
        if role == "STREET":
            spans["STREET"] = (spans["STREET"] + ", " + t) if "STREET" in spans else t
        elif role not in spans:  # keep the first occurrence of an admin role
            spans[role] = t
    return spans


# ---------------------------------------------------------------- rule based
_W = r"(?:phuong|p\.?|f\.?|xa|x\.|thi tran|tt\.?|dac khu)"
_D = r"(?:quan|q\.?|huyen|h\.|thi xa|tx\.?|thanh pho|tp\.?)"
_P = r"(?:tinh|t\.|thanh pho|tp\.?)"


class RuleTagger:
    """Split on separators, then assign chunks by type keyword or by position from the end."""
    name = "rules"

    def spans(self, text: str) -> dict:
        t = NOISE_SUFFIX.sub("", NOISE_PREFIX.sub("", nfc(text)))
        # split on separators; a '.' only separates when it does not end a type abbreviation (P., Q., TP.)
        chunks = [c.strip(" ,.-") for c in re.split(
            r"\s*[,;|]\s*|\s+-\s+|\s+/\s+|(?<!\b[PpQqHhXxFfTt])(?<!\b[Tt][PpTtXx])\.\s+", t)]
        chunks = [c for c in chunks if c]
        if len(chunks) <= 2:  # few separators: also split before type keywords
            out = []
            for c in chunks:
                a = strip_accents(c).lower()
                cuts = [m.start() for m in re.finditer(rf"(?<![\w])(?:{_W}|{_D}|{_P})(?=\s?\w)", a) if m.start() > 0]
                bounds = [0] + cuts + [len(c)]
                out += [c[bounds[i]:bounds[i + 1]].strip(" ,.-") for i in range(len(bounds) - 1)]
            chunks = [c for c in out if c]
        spans, rest, first_admin = {}, [], None
        for i, c in enumerate(chunks):
            a = strip_accents(c).lower()
            first = a.split()[0] if a.split() else ""
            role = None
            if re.match(rf"^{_W}\s?\w", a) and "WARD" not in spans and first not in {"pho", "phan", "pham"}:
                role = "WARD"
            elif re.match(r"^(?:quan|q\.?|huyen|h\.|thi xa|tx\.?)\s?\w", a) and "DISTRICT" not in spans:
                role = "DISTRICT"
            elif re.match(r"^tinh\s", a) and "PROVINCE" not in spans:
                role = "PROVINCE"
            if role:
                spans[role] = c
                first_admin = i if first_admin is None else first_admin
            else:
                rest.append((i, c))
        # unlabelled chunks before the first keyword chunk are street; later ones fill the missing admin
        # roles from the end (province, then district, then ward)
        street = [c for i, c in rest if first_admin is not None and i < first_admin]
        tail = [c for i, c in rest if first_admin is None or i > first_admin]
        order = [r for r in ("PROVINCE", "DISTRICT", "WARD") if r not in spans]
        keep = 1 if first_admin is None else 0  # no keyword at all: the first chunk stays street
        while tail and order and len(tail) > keep:
            spans[order.pop(0)] = tail.pop()
        street += tail
        if street:
            spans["STREET"] = ", ".join(street)
        return spans


# ---------------------------------------------------------------- transformer
class HFTagger:
    """Fine-tuned token classifier (labels on our word tokens, first-subword alignment)."""

    def __init__(self, model_dir: str | Path, device: str | None = None, quantize: bool = False):
        import torch
        from transformers import AutoModelForTokenClassification, AutoTokenizer
        self.torch = torch
        device = device or os.environ.get("VNADDR_DEVICE", "cpu")  # e.g. VNADDR_DEVICE=cuda
        self.tok = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForTokenClassification.from_pretrained(
            model_dir, torch_dtype=torch.float32).to(device).eval()
        if quantize:  # dynamic int8 Linear layers: faster on CPU; less accurate, see reports/int8_check.md
            self.model = torch.quantization.quantize_dynamic(self.model, {torch.nn.Linear}, dtype=torch.qint8)
        self.id2label = self.model.config.id2label
        self.device = device
        self.name = Path(model_dir).resolve().name

    def predict_batch(self, texts):
        texts = [nfc(t) for t in texts]
        toks_list = [tokenize(t) for t in texts]
        words = [[w for w, _, _ in toks] or ["."] for toks in toks_list]
        enc = self.tok(words, is_split_into_words=True, truncation=True, max_length=512,
                       padding=True, return_tensors="pt")
        with self.torch.no_grad():
            logits = self.model(**{k: v.to(self.device) for k, v in enc.items()
                                   if k in ("input_ids", "attention_mask")}).logits
        pred = logits.argmax(-1).cpu().numpy()
        out = []
        for b, toks in enumerate(toks_list):
            labels = ["O"] * len(toks)
            seen = set()
            for i, wid in enumerate(enc.word_ids(b)):
                if wid is not None and wid not in seen and wid < len(toks):
                    seen.add(wid)
                    labels[wid] = self.id2label[int(pred[b, i])]
            out.append((toks, labels))
        return out

    def spans_batch(self, texts):
        texts = [nfc(t) for t in texts]
        return [spans_from_bio(t, toks, labels) for t, (toks, labels) in zip(texts, self.predict_batch(texts))]

    def spans(self, text):
        return self.spans_batch([text])[0]
