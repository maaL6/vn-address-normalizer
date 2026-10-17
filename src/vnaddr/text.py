"""Text helpers: accent stripping, lookup keys, tokenization."""
import re
import unicodedata

_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D")


def to_key(s: str) -> str:
    """'Thành phố Hà Nội' -> 'thanhphohanoi' (same convention as the gazetteer keys)."""
    return re.sub(r"[^a-z0-9]", "", strip_accents(s).lower())


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def tokenize(s: str):
    """Split into word / punctuation tokens with character offsets."""
    s = nfc(s)
    return [(m.group(), m.start(), m.end()) for m in _TOKEN_RE.finditer(s)]
