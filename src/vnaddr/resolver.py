"""Resolve tagged spans (WARD / DISTRICT / PROVINCE / STREET) to gazetteer units and convert
old (63-province, 3-level) addresses to the new (34-province, 2-level) system."""
import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from .gazetteer import PROVINCE_ALIASES, Gazetteer, Unit, num_norm
from .text import strip_accents, tokenize

WARD_PREFIX = {"phuong", "p", "f", "ph", "xa", "x", "thitran", "tt", "dackhu", "dk", "ward"}
DIST_PREFIX = {"quan", "q", "huyen", "h", "thixa", "tx", "thanhpho", "tp", "district", "dist"}
PROV_PREFIX = {"tinh", "t", "thanhpho", "tp", "city"}
MULTI_PREFIX = [("thi", "tran"), ("thi", "xa"), ("thanh", "pho"), ("dac", "khu"), ("t", "p")]
_GLUED = re.compile(r"^(phuong|quan|p|q|f|ph)\.?0*(\d+)$")
NOISE_TAIL = {"vietnam", "vn", "viet nam"}

MIN_SCORE = 0.72
PREFIX_TYPE = {"phuong": "Phường", "p": "Phường", "f": "Phường", "ph": "Phường", "ward": "Phường",
               "xa": "Xã", "x": "Xã", "thitran": "Thị trấn", "tt": "Thị trấn", "dackhu": "Đặc khu", "dk": "Đặc khu",
               "quan": "Quận", "q": "Quận", "district": "Quận", "huyen": "Huyện", "h": "Huyện",
               "thixa": "Thị xã", "tx": "Thị xã", "thanhpho": "Thành phố", "tp": "Thành phố"}
BIG_CITIES = {"thanhphohochiminh", "thanhphohanoi", "thanhphodanang", "thanhphohaiphong", "thanhphocantho",
              "tinhbinhduong", "tinhdongnai"}


def _ascii_tokens(text: str):
    return [strip_accents(t).lower() for t, _, _ in tokenize(text) if re.match(r"\w", t)]


def core_key(text: str, prefixes) -> tuple[str, str | None]:
    """Remove administrative type prefix. Returns (core_key, prefix_key_or_None)."""
    toks = _ascii_tokens(text)
    if not toks:
        return "", None
    if len(toks) == 1:
        m = _GLUED.match(toks[0])
        if m:
            return m.group(2), m.group(1)
    pref = None
    if len(toks) >= 2 and (toks[0], toks[1]) in MULTI_PREFIX:
        if len(toks) == 2:  # the span is only a type word ("Thị trấn")
            return "", toks[0] + toks[1]
        pref, toks = toks[0] + toks[1], toks[2:]
    elif toks[0] in prefixes:
        if len(toks) == 1:  # only a type word ("Phường")
            return "", toks[0]
        pref, toks = toks[0], toks[1:]
    return num_norm("".join(toks)), pref


_EMB_PREFIX = {"phuong", "xa", "p", "f", "tt", "dackhu"}


def embedded_wards(text: str):
    """Ward mentions inside a detail/POI chunk: 'UBND xã Kim Chung' -> ['xã Kim Chung'].
    Returns candidate substrings (last mention first)."""
    out = []
    for piece in (text or "").split(", "):
        words = [(t, s_) for t, s_, _ in tokenize(piece) if re.match(r"\w", t)]
        for i, (t, st) in enumerate(words):
            a = strip_accents(t).lower()
            j = i + 1
            if a == "thi" and i + 1 < len(words) and strip_accents(words[i + 1][0]).lower() == "tran":
                j = i + 2
            elif a not in _EMB_PREFIX:
                continue
            if 1 <= len(words) - j <= 5 and i > 0:  # needs a head word before ('UBND', 'Công an'...)
                out.append(piece[st:])
    return out[::-1]


def initials(name: str) -> str:
    return "".join(w[0] for w in strip_accents(name).lower().split() if w)


@dataclass
class Match:
    unit: Unit
    score: float


def best_matches(core: str, units: dict, k: int = 3, extra: dict | None = None, type_hint: str | None = None):
    """Score every unit in `units` against `core`; returns top-k Match (score in 0..1).
    `type_hint` (e.g. 'Xã' from a 'x.' prefix) slightly penalises units of another type."""
    if isinstance(core, (list, tuple)):  # alternative readings: keep the best score per unit
        best = {}
        for c in core:
            for m in best_matches(c, units, k=k, extra=extra, type_hint=type_hint):
                if m.unit.key not in best or m.score > best[m.unit.key].score:
                    best[m.unit.key] = m
        return sorted(best.values(), key=lambda m: -m.score)[:k]
    if not core:
        return []
    want = PREFIX_TYPE.get(type_hint) if type_hint else None
    out = []
    for key, u in units.items():
        if core == u.short_key or core in u.keywords or (extra and extra.get(core) == key):
            s = 1.0
        else:
            s = fuzz.ratio(core, u.short_key) / 100.0
            if u.short_key and not u.short_key.isdigit() and len(u.short_key) > 4 and core == initials_key(u):
                s = max(s, 0.86)
            if core.isdigit() or u.short_key.isdigit():  # numbers must match exactly
                s = 0.0 if core != u.short_key else 1.0
        if want and u.type and u.type != want and not (want == "Thành phố" and u.type == "Thị xã"):
            s *= 0.9
        if s >= 0.6:
            out.append(Match(u, s))
    out.sort(key=lambda m: -m.score)
    return out[:k]


def initials_key(u: Unit) -> str:
    from .gazetteer import short_name, DISTRICT_TYPES, WARD_TYPES
    return initials(short_name(short_name(u.name, DISTRICT_TYPES), WARD_TYPES))


@dataclass
class Resolution:
    fmt: str | None = None
    old: dict | None = None
    new: dict | None = None
    alternatives: list = field(default_factory=list)
    split_ward: bool = False
    confidence: float = 0.0
    street: str = ""

    def as_dict(self):
        return self.__dict__


class Resolver:
    def __init__(self, gz: Gazetteer):
        self.gz = gz
        # alias -> {province_key: score}; ambiguous initials share a lower score
        self._prov_alias = {k: ({v: 1.0} if isinstance(v, str) else {x: 0.93 for x in v})
                            for k, v in PROVINCE_ALIASES.items()}
        self._alias_single = {k: v for k, v in PROVINCE_ALIASES.items() if isinstance(v, str)}

    # ---------------- province ----------------
    def province_candidates(self, span: str | None):
        """Returns {province_key: score} over the union of old and new province keys."""
        if not span:
            return {}
        core, _ = core_key(span, PROV_PREFIX)
        raw = re.sub(r"[^a-z0-9]", "", strip_accents(span).lower())
        cands = {}
        for units in (self.gz.old_prov, self.gz.new_prov):
            for c in (core, raw):
                for m in best_matches(c, units, k=3, extra=self._alias_single):
                    cands[m.unit.key] = max(cands.get(m.unit.key, 0), m.score)
        for c in (core, raw):
            if c in self._prov_alias:
                for pk, sc in self._prov_alias[c].items():
                    cands[pk] = max(cands.get(pk, 0), sc)
            elif len(c) >= 4:
                for a, pk in self._alias_single.items():
                    if len(a) >= 4:
                        sc = fuzz.ratio(c, a) / 100.0
                        if sc >= 0.85:
                            cands[pk] = max(cands.get(pk, 0), sc * 0.97)
        return {k: v for k, v in cands.items() if v >= MIN_SCORE}

    def _hypotheses(self, provs, prov_given, wcore, wpref, dcore, dpref, ward_search=None):
        gz = self.gz
        hyps = []  # (score, fmt, pk, dk, wk)
        # ---- old-format hypotheses ----
        for pk, sp in provs.items():
            if pk not in gz.old_prov:
                continue
            dists = gz.old_dist[pk]
            dmatches = best_matches(dcore, dists, k=3, type_hint=dpref) if dcore else []
            if dmatches and dmatches[0].score < 0.8 and wcore and prov_given:
                dmatches = []  # weak district match: rather trust the ward (district may be renamed/dissolved)
            if dmatches:
                for dm in dmatches:
                    wards = gz.old_ward.get((pk, dm.unit.key), {})
                    if wcore and wards:
                        for wm in best_matches(wcore, wards, k=2, type_hint=wpref):
                            hyps.append((sp * dm.score * wm.score, "old", pk, dm.unit.key, wm.unit.key))
                    elif wcore:  # island districts (Côn Đảo, Lý Sơn...) have no wards: the district decides
                        hyps.append((sp * dm.score * 0.95, "old", pk, dm.unit.key, None))
                    else:
                        hyps.append((sp * dm.score * 0.9, "old", pk, dm.unit.key, None))
            elif wcore and (prov_given if ward_search is None else ward_search):
                # ward without (usable) district: search the whole province
                pen = 0.85 if ward_search else (0.80 if not dcore else 0.72)
                for dk, _ in dists.items():
                    for wm in best_matches(wcore, gz.old_ward.get((pk, dk), {}), k=1, type_hint=wpref):
                        hyps.append((sp * wm.score * pen, "old", pk, dk, wm.unit.key))
        # ---- new-format hypotheses ----
        if not dcore:
            new_provs, direct = {}, set()
            for pk, sp in provs.items():  # an old province name + a new ward: search its successor
                npk = pk if pk in gz.new_prov else gz.old2new_prov.get(pk)
                if npk:
                    new_provs[npk] = max(new_provs.get(npk, 0), sp if npk == pk else sp * 0.97)
                    if npk == pk:
                        direct.add(pk)
            for pk, sp in new_provs.items():
                if wcore:
                    for wm in best_matches(wcore, gz.new_ward[pk], k=2, type_hint=wpref):
                        hyps.append((sp * wm.score * (1.0 if prov_given else 0.95), "new", pk, None, wm.unit.key))
                elif prov_given and pk in direct:  # province only
                    hyps.append((sp * 0.5, "new", pk, None, None))
        elif not hyps:  # district span did not match anything: maybe tagger mislabelled a new ward
            for pk, sp in provs.items():
                if pk in gz.new_prov:
                    for wm in best_matches(dcore, gz.new_ward[pk], k=1):
                        hyps.append((sp * wm.score * 0.7, "new", pk, None, wm.unit.key))
        return hyps

    @staticmethod
    def _cores(span, prefixes):
        """('Phương Mai') -> (['mai', 'phuongmai'], 'phuong'): the first word may be a type prefix
        ('Phường') or part of the name ('Phương Mai'), so both readings are kept."""
        if not span:
            return "", None
        core, pref = core_key(span, prefixes)
        if pref is None:
            return core, None
        full = num_norm("".join(_ascii_tokens(span)))
        if not core or core.isdigit():  # 'Phường 12' is never a name like 'Phường12...'
            return core, pref
        return ([core, full] if full != core else core), pref

    def _candidates(self, provs, prov_given, wcore, wpref, dcore, dpref, ward_search=None):
        hyps = self._hypotheses(provs, prov_given, wcore, wpref, dcore, dpref, ward_search)
        if dcore and not wcore and dpref is None:
            # an un-prefixed lone span may be a ward (new 2-level address) rather than a district
            hyps += [(h[0] * 0.97,) + h[1:]
                     for h in self._hypotheses(provs, prov_given, dcore, None, "", None, ward_search)]
        return hyps

    def _final(self, h):
        """New (province, default ward) a hypothesis leads to."""
        _, fmt, pk, dk, wk = h
        if fmt == "new":
            return pk, wk
        npk, cands = self.gz.convert(pk, dk, wk)
        return npk, next((c[0] for c in cands if c[1]), None)

    # ---------------- main ----------------
    def resolve(self, spans: dict) -> Resolution:
        gz = self.gz
        ward_span = spans.get("WARD")
        dist_span = spans.get("DISTRICT")
        prov_span = spans.get("PROVINCE")
        res = Resolution(street=spans.get("STREET", ""))

        provs = self.province_candidates(prov_span)
        prov_given = bool(provs)
        if not provs:  # unknown province -> search everywhere, with a penalty
            provs = {pk: (0.85 if pk in BIG_CITIES else 0.80) for pk in set(gz.old_prov) | set(gz.new_prov)}

        wcore, wpref = self._cores(ward_span, WARD_PREFIX)
        dcore, dpref = self._cores(dist_span, DIST_PREFIX)

        hyps = self._candidates(provs, prov_given, wcore, wpref, dcore, dpref)
        if not hyps or max(h[0] for h in hyps) < 0.85 or not wcore:
            # the ward may only be mentioned inside a POI ('UBND xã Kim Chung, Đông Anh, HN')
            street = spans.get("STREET", "")
            embedded = embedded_wards(street)
            if ward_span and wpref is None:  # tagger may have cut the POI in two ('...xã Sen' + 'Phương')
                embedded += embedded_wards(street.split(", ")[-1] + " " + ward_span) if street else []
            for emb in embedded[:2]:
                ec, ep = self._cores(emb, WARD_PREFIX)
                hyps += [(h[0] * 0.97,) + h[1:] for h in self._candidates(provs, prov_given, ec, ep, dcore, dpref)]
                if ward_span and not dcore and wpref is None:  # then the lone un-prefixed span is the district
                    hyps += [(h[0] * 0.95,) + h[1:]
                             for h in self._candidates(provs, prov_given, ec, ep, wcore, None)]
        if prov_given and (not hyps or max(h[0] for h in hyps) < 0.8) and (wcore or dcore):
            # the province span may be wrong (typo, mis-tagged POI): search the whole country
            every = {pk: (0.84 if pk in BIG_CITIES else 0.82) for pk in set(gz.old_prov) | set(gz.new_prov)}
            hyps += self._candidates(every, False, wcore, wpref, dcore, dpref, ward_search=True)
        if not hyps:
            if prov_given:  # at least the province
                pk, sp = max(provs.items(), key=lambda kv: kv[1])
                npk = pk if pk in gz.new_prov else gz.old2new_prov.get(pk)
                res.fmt = "old" if pk not in gz.new_prov else None
                if pk not in gz.new_prov:
                    res.old = {"province": gz.old_prov[pk].name, "province_key": pk, "district": None,
                               "district_key": None, "ward": None, "ward_key": None}
                res.new = {"province": gz.new_prov[npk].name, "province_key": npk, "ward": None, "ward_key": None}
                res.confidence = round(sp * 0.3, 3)
            return res

        hyps.sort(key=lambda h: -h[0])
        score, fmt, pk, dk, wk = hyps[0]
        # ambiguity penalty: runner-up with a different final ward and a close score
        margin = 1.0
        best_final = self._final(hyps[0])
        for h in hyps[1:]:
            if self._final(h) != best_final:
                margin = min(1.0, 0.5 + (score - h[0]) * 5)
                break
        res.fmt = fmt
        if fmt == "old":
            res.old = {"province": gz.old_prov[pk].name, "district": gz.old_dist[pk][dk].name,
                       "ward": gz.old_ward[(pk, dk)][wk].name if wk else None,
                       "province_key": pk, "district_key": dk, "ward_key": wk}
            npk, cands = gz.convert(pk, dk, wk)
            default = next((c[0] for c in cands if c[1]), None)
            res.new = {"province": gz.new_prov[npk].name, "province_key": npk,
                       "ward": gz.new_ward[npk][default].name if default else None, "ward_key": default}
            if len(cands) > 1:
                res.split_ward = True
                res.alternatives = [{"ward": gz.new_ward[npk][c[0]].name, "ward_key": c[0], "default": c[1]}
                                    for c in cands]
                score *= 0.8
        else:
            res.new = {"province": gz.new_prov[pk].name, "province_key": pk,
                       "ward": gz.new_ward[pk][wk].name if wk else None, "ward_key": wk}
        res.confidence = round(score * margin, 3)
        n = res.new
        res.new["full_address"] = ", ".join(x for x in (res.street, n["ward"], n["province"]) if x)
        return res
