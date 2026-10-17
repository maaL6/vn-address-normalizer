"""Administrative-unit gazetteer (old 3-level and new 2-level) + official old->new mapping."""
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .text import to_key

DATA = Path(__file__).resolve().parents[2] / "data" / "gazetteer.json"

# type prefixes (as keys) that can precede a unit name
WARD_TYPES = {"Phường": "phuong", "Xã": "xa", "Thị trấn": "thitran", "Đặc khu": "dackhu"}
DISTRICT_TYPES = {"Quận": "quan", "Huyện": "huyen", "Thị xã": "thixa", "Thành phố": "thanhpho"}
PROVINCE_TYPES = {"Tỉnh": "tinh", "Thành phố": "thanhpho"}

# informal province names seen in the wild (key -> province key, valid for both eras
# unless the province only exists in one of them)
PROVINCE_ALIASES = {
    "saigon": "thanhphohochiminh", "sg": "thanhphohochiminh", "tphcm": "thanhphohochiminh",
    "hcmc": "thanhphohochiminh", "tpsaigon": "thanhphohochiminh", "hcm": "thanhphohochiminh",
    "hn": "thanhphohanoi", "tphn": "thanhphohanoi", "hanoi": "thanhphohanoi",
    "brvt": "tinhbariavungtau", "bariavungtau": "tinhbariavungtau",
    "thuathienhue": "thanhphohue", "tthue": "thanhphohue", "hue": "thanhphohue",
    "tpdn": "thanhphodanang", "hp": "thanhphohaiphong",
    "ct": "thanhphocantho", "daklak": "tinhdaklak", "daclac": "tinhdaklak", "daklac": "tinhdaklak",
    "dacnong": "tinhdaknong", "kontum": "tinhkontum",
    # ambiguous initials: resolved by the ward/district that follow
    "dn": ("thanhphodanang", "tinhdongnai"), "bd": ("tinhbinhduong", "tinhbinhdinh"), "bp": "tinhbinhphuoc",
    "kg": "tinhkiengiang", "ag": "tinhangiang", "ld": "tinhlamdong", "dt": "tinhdongthap",
    "qn": ("tinhquangninh", "tinhquangnam", "tinhquangngai"), "qnam": "tinhquangnam", "th": "tinhthanhhoa",
    "na": "tinhnghean", "kh": "tinhkhanhhoa", "la": "tinhlongan", "tg": "tinhtiengiang",
}


def short_name(name: str, types) -> str:
    for t in sorted(types, key=len, reverse=True):
        if name.startswith(t + " "):
            return name[len(t) + 1:]
    return name


def strip_type_key(key: str, type_keys) -> str:
    for t in sorted(type_keys, key=len, reverse=True):
        if key.startswith(t) and len(key) > len(t):
            return key[len(t):]
    return key


def num_norm(key: str) -> str:
    """'01' -> '1' so that 'Phường 01' == 'Phường 1'."""
    return re.sub(r"(?<![0-9])0+(?=[0-9])", "", key)


@dataclass
class Unit:
    name: str
    key: str
    type: str | None
    short_key: str
    keywords: set = field(default_factory=set)
    lat: float | None = None
    lon: float | None = None


class Gazetteer:
    def __init__(self, path: Path = DATA):
        g = json.loads(Path(path).read_text())
        self.source = g["source"]
        # ---- old (pre-2025) ----
        self.old_prov: dict[str, Unit] = {}
        self.old_dist: dict[str, dict[str, Unit]] = {}
        self.old_ward: dict[tuple, dict[str, Unit]] = {}
        for r in g["old"]:
            pk, dk, wk = r["pk"], r["dk"], r["wk"]
            if pk not in self.old_prov:
                self.old_prov[pk] = Unit(r["p"], pk, None, num_norm(strip_type_key(pk, PROVINCE_TYPES.values())),
                                         set(r["pkw"]))
            dd = self.old_dist.setdefault(pk, {})
            if dk not in dd:
                dd[dk] = Unit(r["d"], dk, r["dtype"], num_norm(to_key(short_name(r["d"], DISTRICT_TYPES))),
                              {num_norm(k) for k in r["dkw"]})
            if wk:
                self.old_ward.setdefault((pk, dk), {})[wk] = Unit(
                    r["w"], wk, r["wtype"], num_norm(to_key(short_name(r["w"], WARD_TYPES))),
                    {num_norm(k) for k in r["wkw"]}, r["lat"], r["lon"])
            else:
                self.old_ward.setdefault((pk, dk), {})
        # ---- new (from 1/7/2025) ----
        self.new_prov: dict[str, Unit] = {}
        self.new_ward: dict[str, dict[str, Unit]] = {}
        for r in g["new"]:
            pk = r["pk"]
            if pk not in self.new_prov:
                self.new_prov[pk] = Unit(r["p"], pk, None, strip_type_key(pk, PROVINCE_TYPES.values()),
                                         set(r["pkw"]))
            self.new_ward.setdefault(pk, {})[r["wk"]] = Unit(
                r["w"], r["wk"], r["wtype"], num_norm(to_key(short_name(r["w"], WARD_TYPES))),
                {num_norm(k) for k in r["wkw"]}, r["lat"], r["lon"])
        # ---- mapping ----
        self.old2new_prov = {o: n for n, olds in g["province_map"].items() for o in olds}
        self._nodiv = {}
        for npk, wards in g["nodiv"].items():
            for nwk, olds in wards.items():
                for ok in olds:
                    self._nodiv[ok] = (npk, nwk)
        self._div = {ok: (npk, lst) for npk, d in g["div"].items() for ok, lst in d.items()}

    # ------------------------------------------------------------------
    def convert(self, pk: str, dk: str | None, wk: str | None):
        """Map an old unit to new ones.

        Returns (new_province_key, [(new_ward_key, is_default), ...]). The ward list is empty
        when the old ward is unknown; it has >1 entries when the old ward was split.
        """
        npk = self.old2new_prov.get(pk)
        if npk is None:
            return None, []
        if dk is None:
            return npk, []
        okey = f"{pk}_{dk}_{wk or ''}"
        if okey in self._nodiv:
            return npk, [(self._nodiv[okey][1], True)]
        if okey in self._div:
            _, lst = self._div[okey]
            return npk, [(x["newWardKey"], bool(x["isDefaultNewWard"])) for x in lst]
        return npk, []

    def old_full(self, pk, dk, wk):
        parts = []
        if wk:
            parts.append(self.old_ward[(pk, dk)][wk].name)
        if dk:
            parts.append(self.old_dist[pk][dk].name)
        parts.append(self.old_prov[pk].name)
        return ", ".join(parts)

    def new_full(self, pk, wk):
        parts = [self.new_ward[pk][wk].name] if wk else []
        parts.append(self.new_prov[pk].name)
        return ", ".join(parts)


@lru_cache(maxsize=1)
def load() -> Gazetteer:
    return Gazetteer()
