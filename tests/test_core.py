import pytest

from vnaddr.gazetteer import load
from vnaddr.resolver import Resolver, core_key, WARD_PREFIX, DIST_PREFIX
from vnaddr.synth import Generator
from vnaddr.tagger import RuleTagger, spans_from_bio
from vnaddr.text import strip_accents, to_key, tokenize


@pytest.fixture(scope="module")
def gz():
    return load()


@pytest.fixture(scope="module")
def res(gz):
    return Resolver(gz)


def test_text_helpers():
    assert strip_accents("Đống Đa") == "Dong Da"
    assert to_key("Thành phố Hà Nội") == "thanhphohanoi"
    assert [t for t, _, _ in tokenize("P.12, Q1")] == ["P", ".", "12", ",", "Q1"]


def test_core_key_prefixes():
    assert core_key("P.12", WARD_PREFIX) == ("12", "p")
    assert core_key("Phường 01", WARD_PREFIX)[0] == "1"
    assert core_key("thi tran Cu Chi", WARD_PREFIX) == ("cuchi", "thitran")
    assert core_key("Q1", DIST_PREFIX) == ("1", "q")


def test_gazetteer_sizes_and_full_mapping(gz):
    assert len(gz.old_prov) == 63 and len(gz.new_prov) == 34
    assert sum(len(v) for v in gz.new_ward.values()) == 3321
    for (pk, dk), wards in gz.old_ward.items():
        for wk in wards or [None]:
            npk, cands = gz.convert(pk, dk, wk)
            assert npk in gz.new_prov and cands, (pk, dk, wk)


def test_province_merge(gz):
    assert gz.old2new_prov["tinhbinhduong"] == "thanhphohochiminh"
    assert gz.old2new_prov["tinhyenbai"] == "tinhlaocai"


def test_resolve_old_address(res):
    r = res.resolve({"STREET": "1 Đại Cồ Việt", "WARD": "p bach khoa", "DISTRICT": "q hai ba trung",
                     "PROVINCE": "hn"})
    assert r.fmt == "old"
    assert r.old["ward_key"] == "phuongbachkhoa" and r.old["district_key"] == "quanhaibatrung"
    assert r.new["province_key"] == "thanhphohanoi" and r.new["ward_key"]
    assert r.new["full_address"].startswith("1 Đại Cồ Việt, ")


def test_resolve_new_address(res):
    r = res.resolve({"WARD": "Phường Sài Gòn", "PROVINCE": "TP.HCM"})
    assert r.fmt == "new" and r.new["ward_key"] == "phuongsaigon"


def test_resolve_merged_province(res):
    r = res.resolve({"WARD": "P.Phú Cường", "DISTRICT": "TP Thủ Dầu Một", "PROVINCE": "Bình Dương"})
    assert r.old["province_key"] == "tinhbinhduong" and r.new["province_key"] == "thanhphohochiminh"


def test_resolve_typo_and_no_accent(res):
    r = res.resolve({"WARD": "phuong phuong mia", "DISTRICT": "quan dong da", "PROVINCE": "ha noi"})
    assert r.old and r.old["ward_key"] == "phuongphuongmai"


def test_split_ward_has_alternatives(gz, res):
    okey = next(iter(gz._div))
    pk, dk, wk = okey.split("_")
    r = res.resolve({"WARD": gz.old_ward[(pk, dk)][wk].name, "DISTRICT": gz.old_dist[pk][dk].name,
                     "PROVINCE": gz.old_prov[pk].name})
    assert r.split_ward and len(r.alternatives) >= 2 and sum(a["default"] for a in r.alternatives) == 1


def test_unknown_address_is_safe(res):
    r = res.resolve({"STREET": "asdkjh"})
    assert r.new is None and r.confidence == 0


def test_generator_labels_align(gz):
    g = Generator(gz, seed=7)
    for _ in range(300):
        s = g.sample()
        assert [t for t, _, _ in tokenize(s["text"])] == s["tokens"]
        assert len(s["tokens"]) == len(s["labels"])
        assert s["new_pk"] in gz.new_prov


def test_gold_spans_resolve_well(gz, res):
    g = Generator(gz, seed=11)
    ok = n = 0
    for _ in range(300):
        s = g.sample()
        if not s["new_wards"]:
            continue
        r = res.resolve(spans_from_bio(s["text"], tokenize(s["text"]), s["labels"]))
        n += 1
        ok += bool(r.new) and r.new["province_key"] == s["new_pk"] and r.new["ward_key"] in s["new_wards"]
    assert ok / n > 0.95


def test_rule_tagger_basic():
    sp = RuleTagger().spans("12 Nguyễn Trãi, Phường Bến Thành, Quận 1, TP.HCM")
    assert sp["WARD"] == "Phường Bến Thành" and sp["DISTRICT"] == "Quận 1" and sp["PROVINCE"] == "TP.HCM"
