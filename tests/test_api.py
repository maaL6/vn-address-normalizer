from fastapi.testclient import TestClient

from vnaddr.api import app


def test_api_roundtrip():
    with TestClient(app) as c:
        assert c.get("/health").json()["status"] == "ok"
        r = c.post("/normalize", json={"address": "12 Nguyễn Trãi, Phường Bến Thành, Quận 1, TP.HCM"})
        assert r.status_code == 200
        d = r.json()
        assert d["new"]["province_key"] == "thanhphohochiminh"
        assert d["new"]["ward_key"] == "phuongbenthanh"
        b = c.post("/normalize/batch", json={"addresses": ["Phường Sài Gòn, TP.HCM", "???"]})
        assert b.status_code == 200 and len(b.json()["results"]) == 2
        assert c.post("/normalize", json={"address": ""}).status_code == 422
        assert c.get("/").status_code == 200
