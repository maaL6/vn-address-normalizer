"""End-to-end: raw address -> spans -> resolved old/new administrative units."""
import os
import sys
from pathlib import Path

from .gazetteer import load
from .resolver import Resolver
from .tagger import HFTagger, RuleTagger

DEFAULT_MODEL = Path(__file__).resolve().parents[2] / "models" / "tagger"


class Normalizer:
    def __init__(self, model_dir: str | Path | None = None, use_model: bool = True):
        self.gz = load()
        self.resolver = Resolver(self.gz)
        model_dir = Path(model_dir or os.environ.get("VNADDR_MODEL", DEFAULT_MODEL))
        if use_model and (model_dir / "config.json").exists():
            self.tagger = HFTagger(model_dir)
        else:
            if use_model:
                print(f"vnaddr: no model in {model_dir}, using the rule-based splitter (much less accurate)",
                      file=sys.stderr)
            self.tagger = RuleTagger()
        self.uses_model = isinstance(self.tagger, HFTagger)

    def _finish(self, text, spans):
        r = self.resolver.resolve(spans).as_dict()
        return {"input": text, "spans": spans, **r}

    def normalize(self, text: str) -> dict:
        return self._finish(text, self.tagger.spans(text))

    def normalize_batch(self, texts, batch_size: int = 64):
        out = []
        for i in range(0, len(texts), batch_size):
            chunk = texts[i:i + batch_size]
            spans = self.tagger.spans_batch(chunk) if hasattr(self.tagger, "spans_batch") else [
                self.tagger.spans(t) for t in chunk]
            out.extend(self._finish(t, s) for t, s in zip(chunk, spans))
        return out
