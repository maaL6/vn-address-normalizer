"""Regression tests for bugs found in code review."""
import csv
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vnaddr.api import app
from vnaddr.gazetteer import load
from vnaddr.resolver import Resolver, core_key, WARD_PREFIX
from vnaddr.tagger import RuleTagger, spans_from_bio
from vnaddr.text import tokenize

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def res():
    return Resolver(load())


@pytest.mark.parametrize("spans,ward", [
    ({"WARD": "Xã An Vĩnh", "DISTRICT": "Huyện Lý Sơn", "PROVINCE": "Quảng Ngãi"}, "dackhulyson"),
    ({"WARD": "Thị trấn Côn Đảo", "DISTRICT": "Huyện Côn Đảo", "PROVINCE": "BRVT"}, "dackhucondao"),
    ({"WARD": "Xã Gia Lâm", "PROVINCE": "Hà Nam"}, "xagialam"),            # new ward + merged-away province
    ({"WARD": "Phương Mai", "DISTRICT": "Đống Đa", "PROVINCE": "Hà Nội"}, None),  # name starting like a prefix
    ({"WARD": "Phường 12", "DISTRICT": "Quận Gò Vấp", "PROVINCE": "HCM"}, None),
])
def test_resolver_regressions(res, spans, ward):
    r = res.resolve(spans)
    assert r.new and r.new["ward_key"]
    if ward:
        assert r.new["ward_key"] == ward
    if "Phương Mai" in spans.get("WARD", ""):
        assert r.old["ward_key"] == "phuongphuongmai"
    if "Phường 12" in spans.get("WARD", ""):
        assert r.old["ward_key"] == "phuong12" and r.old["district_key"] == "quangovap"


def test_type_word_only_span_is_empty(res):
    assert core_key("Phường", WARD_PREFIX) == ("", "phuong")
    r = res.resolve({"WARD": "Phường", "DISTRICT": "Quận 1", "PROVINCE": "HCM"})
    assert r.fmt == "old" and r.old["district_key"] == "quan1"


def test_old_province_only(res):
    r = res.resolve({"PROVINCE": "Bình Dương"})
    assert r.fmt == "old" and r.old["province_key"] == "tinhbinhduong"
    assert r.new["province_key"] == "thanhphohochiminh" and r.new["ward"] is None


def test_nfd_input_spans_are_clean():
    text = unicodedata.normalize("NFD", "Phường Bến Thành, Quận 1, TP.HCM")
    sp = RuleTagger().spans(text)
    assert sp["WARD"] == unicodedata.normalize("NFC", "Phường Bến Thành")


@pytest.mark.parametrize("text,expected", [
    ("12 Ngô Quyền, Phường Sài Gòn, TP.HCM", {"STREET": "12 Ngô Quyền", "WARD": "Phường Sài Gòn",
                                              "PROVINCE": "TP.HCM"}),
    ("5 Lê Lợi, P. Bến Nghé, Q. 1, HCM", {"STREET": "5 Lê Lợi", "WARD": "P. Bến Nghé", "DISTRICT": "Q. 1",
                                          "PROVINCE": "HCM"}),
    ("Phường 7, Quận 3, TP HCM", {"WARD": "Phường 7", "DISTRICT": "Quận 3", "PROVINCE": "TP HCM"}),
])
def test_rule_tagger_cases(text, expected):
    assert RuleTagger().spans(text) == expected


def test_spans_from_bio_joins_street_pieces():
    text = "Tổ 5, Ấp 3, Xã Tân Thông Hội"
    toks = tokenize(text)
    labels = ["B-STREET", "I-STREET", "O", "B-STREET", "I-STREET", "O", "B-WARD", "I-WARD", "I-WARD", "I-WARD"]
    assert spans_from_bio(text, toks, labels) == {"STREET": "Tổ 5, Ấp 3", "WARD": "Xã Tân Thông Hội"}


def test_api_batch_validation():
    with TestClient(app) as c:
        assert c.post("/normalize/batch", json={"addresses": ["ok", "   "]}).status_code == 422
        assert c.post("/normalize/batch", json={"addresses": []}).status_code == 422
        assert c.post("/normalize/batch", json={"addresses": ["x" * 501]}).status_code == 422


def test_cli_csv(tmp_path):
    src = tmp_path / "in.csv"
    src.write_text("id,address,new_ward\n1,\"Phường Bến Thành, Quận 1, TP.HCM\",keep\n2\n", encoding="utf-8")
    out = tmp_path / "out.csv"
    p = subprocess.run([sys.executable, "-m", "vnaddr", "--rules", "--csv", str(src), "--out", str(out)],
                       cwd=ROOT, env={"PYTHONPATH": str(ROOT / "src"), "PATH": ""}, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert rows[0]["new_ward"] == "keep"  # input column not overwritten
    assert rows[0]["vnaddr_new_ward"] == "Phường Bến Thành"
    assert rows[1]["vnaddr_new_ward"] == ""  # short row handled


def test_score_counts_split_candidates():
    sys.path.insert(0, str(ROOT / "scripts"))
    from evaluate import score
    rows = [{"new_pk": "a", "new_wards": ["w1", "w2"], "new_default": "w1", "fmt": "old"},
            {"new_pk": "a", "new_wards": [], "new_default": None, "fmt": "old"}]
    sc = score(rows, [("a", "w2", None, "old"), ("a", None, None, None)])
    assert sc["province"] == 100.0 and sc["ward_in_candidates"] == 100.0 and sc["ward_default"] == 0.0


def test_cli_summary_and_json():
    env = {"PYTHONPATH": str(ROOT / "src"), "PATH": "", "VNADDR_MODEL": "/nonexistent"}
    p = subprocess.run([sys.executable, "-m", "vnaddr", "12 Nguyễn Trãi, Phường Bến Thành, Quận 1, TP.HCM"],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    assert p.returncode == 0
    assert "new: 12 Nguyễn Trãi, Phường Bến Thành, Thành phố Hồ Chí Minh" in p.stdout
    assert "rule-based splitter" in p.stderr  # fallback is announced
    p = subprocess.run([sys.executable, "-m", "vnaddr", "--json", "Phường Sài Gòn, TP.HCM"],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    import json
    assert json.loads(p.stdout)["new"]["ward_key"] == "phuongsaigon"
