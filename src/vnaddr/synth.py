"""Synthetic noisy Vietnamese address generator with token-level BIO labels.

Each sample mimics how people actually type addresses (no diacritics, abbreviations,
missing commas, typos, informal province names...) in either the old 3-level format
(ward, district, province) or the new 2-level format (ward, province) in force since 1/7/2025.
"""
import random

from .gazetteer import Gazetteer, DISTRICT_TYPES, WARD_TYPES, short_name
from .text import strip_accents, tokenize

LABELS = ["O", "B-STREET", "I-STREET", "B-WARD", "I-WARD", "B-DISTRICT", "I-DISTRICT",
          "B-PROVINCE", "I-PROVINCE"]

STREETS = """Lê Lợi|Nguyễn Huệ|Trần Hưng Đạo|Lý Thường Kiệt|Hai Bà Trưng|Lê Duẩn|Nguyễn Trãi|Quang Trung|
Trần Phú|Lê Thánh Tông|Nguyễn Du|Phan Chu Trinh|Phan Bội Châu|Nguyễn Thị Minh Khai|Võ Thị Sáu|Điện Biên Phủ|
Cách Mạng Tháng Tám|Nam Kỳ Khởi Nghĩa|Pasteur|Lê Văn Sỹ|Hoàng Văn Thụ|Cộng Hòa|Trường Chinh|Âu Cơ|Lạc Long Quân|
Nguyễn Văn Linh|Nguyễn Văn Cừ|Nguyễn Thái Học|Tôn Đức Thắng|Tôn Thất Tùng|Giải Phóng|Láng|Láng Hạ|Xã Đàn|
Kim Mã|Đội Cấn|Hoàng Quốc Việt|Phạm Văn Đồng|Xuân Thủy|Cầu Giấy|Trần Duy Hưng|Nguyễn Chí Thanh|Bạch Mai|
Minh Khai|Tam Trinh|Lĩnh Nam|Nguyễn Văn Cừ|Ngọc Lâm|Hùng Vương|Lê Hồng Phong|Ngô Quyền|Bà Triệu|Hàng Bài|
Tràng Tiền|Hàng Bạc|Hàng Đào|Phố Huế|Thái Hà|Chùa Bộc|Tây Sơn|Đào Duy Anh|Nguyễn Lương Bằng|Khâm Thiên|
Lê Văn Việt|Võ Văn Ngân|Kha Vạn Cân|Xa Lộ Hà Nội|Mai Chí Thọ|Nguyễn Duy Trinh|Đỗ Xuân Hợp|Lũy Bán Bích|
Tân Kỳ Tân Quý|Kinh Dương Vương|Hậu Giang|Hồng Bàng|An Dương Vương|Nguyễn Tri Phương|Ba Tháng Hai|Sư Vạn Hạnh|
Thành Thái|Tô Hiến Thành|Bùi Viện|Đề Thám|Phạm Ngũ Lão|Cô Bắc|Cô Giang|Huỳnh Tấn Phát|Nguyễn Hữu Thọ|
Phan Xích Long|Phan Đăng Lưu|Nơ Trang Long|Xô Viết Nghệ Tĩnh|Bạch Đằng|Đinh Tiên Hoàng|Lê Quang Định|
Quang Trung|Nguyễn Oanh|Phan Văn Trị|Nguyễn Kiệm|Hoàng Hoa Thám|Trần Quang Khải|Nguyễn Văn Trỗi|Lê Đại Hành|
Ông Ích Khiêm|Hoàng Diệu|Lê Lai|Yersinia|Trần Cao Vân|Hàm Nghi|Duy Tân|Núi Thành|Nguyễn Văn Thoại|Võ Nguyên Giáp|
Ngũ Hành Sơn|Lê Văn Hiến|Tôn Đức Thắng|Nguyễn Sinh Sắc|Âu Lạc|Mậu Thân|Ba Tháng Hai|Trần Văn Khéo|Ninh Kiều|
Lạch Tray|Văn Cao|Lê Chân|Tô Hiệu|Trần Nguyên Hãn|Cát Bi|Nguyễn Văn Trỗi|Bà Rịa|Thùy Vân|Thống Nhất|
Phạm Văn Thuận|Đồng Khởi|Võ Thị Sáu|Lê Hoàn|Bùi Thị Xuân|Phan Đình Phùng|Ba Cu|Yersin|Trần Hưng Đạo|
Nguyễn Tất Thành|Lê Thánh Tôn|Hàn Thuyên|Mạc Đĩnh Chi|Chu Văn An|Ngô Gia Tự|Lý Tự Trọng|Lý Thái Tổ|
Hoàng Diệu|Lê Văn Tám|Nguyễn Đình Chiểu|Trương Định|Võ Văn Tần|Nguyễn Văn Bá|Lê Văn Lương|Tố Hữu|
Quốc lộ 1A|Quốc lộ 13|Quốc lộ 22|Quốc lộ 51|Tỉnh lộ 10|Đại lộ Bình Dương|Đại lộ Thăng Long|Vành Đai 3|
Mỹ Đình|Hồ Tùng Mậu|Trần Thái Tông|Duy Tân|Dịch Vọng Hậu|Nguyễn Phong Sắc|Thụy Khuê|Âu Cơ|Lạc Long Quân|
Nguyễn Hoàng|Tân Mai|Giáp Bát|Kim Giang|Ngọc Hồi|Quang Lãm|Tô Hiệu|Hà Huy Tập|Phan Văn Hớn""".replace("\n", "").split("|")

VILLAGE_NAMES = """Đông|Tây|Nam|Bắc|Thượng|Hạ|Trung|An Phú|Tân Hòa|Phú Lợi|Hòa Bình|Bình Minh|Tân Lập|Đồng Tâm|
Thanh Bình|Phú Mỹ|Long Hòa|Mỹ Lợi|Tân Thành|Bình An|Xuân Lộc|Hưng Long|Phước Hòa|Vĩnh Thạnh|Đoàn Kết|Quyết Thắng|
Na Hang|Pác Bó|Nà Phặc|Cốc Lếu|Kim Sơn|Văn Lâm|Đại Đồng|Hòa Lạc|Phú Thượng|Vạn Phúc""".replace("\n", "").split("|")

BUILDINGS = ["Landmark 81", "Bitexco", "Keangnam", "Vincom Center", "Times City", "Royal City", "Sunrise City",
             "Masteri", "Vinhomes Central Park", "Lotte Center", "Saigon Centre", "Pearl Plaza", "Indochina Plaza",
             "Charmvit", "Golden Palace", "The Manor", "Ehome 3", "HH4C Linh Đàm", "CT1 Văn Khê", "Hoàng Anh Gia Lai"]

POI_TEMPLATES = """Bệnh viện {X}|BV {X}|Bệnh viện Đa khoa {AD}|BV đa khoa {AD}|Trung tâm Y tế {AD}|TTYT {AD}|Trường ĐH {X}|
Đại học {X}|Trường THPT {X}|Trường Tiểu học {X}|Chợ {X}|Chợ {AW}|Siêu thị {X}|Chùa {X}|Đền {X}|Nhà thờ {X}|Đình {X}|
UBND {AD}|UBND {AW}|Công an {AW}|Công ty TNHH {X}|Cty CP {X}|Công ty TNHH MTV {X}|KCN {X}|Khu công nghiệp {X}|
Sân bay {X}|Bến xe {X}|Ga {X}|Cảng {X}|Bảo tàng {X}|Khu di tích {X}|Vườn quốc gia {X}|Làng {X}|Hồ {X}|
Cửa khẩu {X}|Khách sạn {X}|Nhà văn hóa {X}|Bưu điện {AD}|Ngân hàng {X} chi nhánh {X}|Vincom {X}|Co.opmart {X}|
Bách hóa Xanh {X}|Circle K {X}|Highlands Coffee {X}|Shop {X}|Cửa hàng {X}|Tiệm {X}|Nhà hàng {X}""".replace("\n", "").split("|")
PROVINCE_INITIALS = {"thanhphodanang": ["ĐN"], "tinhdongnai": ["ĐN"], "tinhbinhduong": ["BD"], "tinhbinhdinh": ["BĐ"],
                     "tinhbinhphuoc": ["BP"], "tinhkiengiang": ["KG"], "tinhangiang": ["AG"], "tinhlamdong": ["LĐ"],
                     "tinhdongthap": ["ĐT"], "tinhquangninh": ["QN"], "tinhquangnam": ["QNam"], "tinhthanhhoa": ["TH"],
                     "tinhnghean": ["NA"], "tinhkhanhhoa": ["KH"], "tinhlongan": ["LA"], "tinhtiengiang": ["TG"]}

WARD_TYPE_VARIANTS = {
    "Phường": [("Phường ", 30), ("P.", 14), ("P. ", 8), ("P ", 8), ("p.", 5), ("p ", 4), ("phường ", 6),
               ("F.", 2), ("Ph. ", 2), ("", 12)],
    "Xã": [("Xã ", 45), ("X.", 10), ("x.", 4), ("xã ", 8), ("X ", 3), ("", 18)],
    "Thị trấn": [("Thị trấn ", 40), ("TT.", 18), ("TT ", 10), ("tt ", 4), ("T.T ", 3), ("thị trấn ", 6), ("", 10)],
    "Đặc khu": [("Đặc khu ", 70), ("ĐK ", 5), ("", 15)],
}
WARD_NUM_VARIANTS = ["Phường {n}", "P.{n}", "P{n}", "P.{n0}", "Phường {n0}", "F{n}", "F.{n}", "p{n}", "P {n}", "phường {n}"]
DIST_TYPE_VARIANTS = {
    "Quận": [("Quận ", 35), ("Q.", 20), ("Q. ", 8), ("Q ", 8), ("q.", 5), ("quận ", 7), ("", 10)],
    "Huyện": [("Huyện ", 40), ("H.", 18), ("H. ", 6), ("h.", 4), ("huyện ", 8), ("", 15)],
    "Thị xã": [("Thị xã ", 40), ("TX.", 20), ("TX ", 12), ("tx ", 5), ("thị xã ", 6), ("", 10)],
    "Thành phố": [("Thành phố ", 35), ("TP.", 20), ("TP ", 12), ("Tp.", 8), ("tp ", 5), ("T.P ", 2), ("", 12)],
}
DIST_NUM_VARIANTS = ["Quận {n}", "Q.{n}", "Q{n}", "Q {n}", "Quận {n0}", "q{n}", "quận {n}", "Q.{n0}", "District {n}"]
SEPARATORS = [(", ", 52), (",", 10), (" - ", 9), (" ", 15), (". ", 3), (" ,", 3), (" , ", 3), ("; ", 2), (" / ", 2)]
PROVINCE_SPECIAL = {
    "thanhphohochiminh": ["Thành phố Hồ Chí Minh", "TP.HCM", "TP. Hồ Chí Minh", "TPHCM", "Hồ Chí Minh", "HCM",
                          "TP HCM", "Sài Gòn", "SG", "tp.hcm", "Tp Hồ Chí Minh", "TP.HỒ CHÍ MINH", "HCMC", "Saigon"],
    "thanhphohanoi": ["Thành phố Hà Nội", "Hà Nội", "TP. Hà Nội", "HN", "TP Hà Nội", "Ha Noi", "Hanoi", "hà nội",
                      "TP.Hà Nội"],
    "thanhphodanang": ["Thành phố Đà Nẵng", "Đà Nẵng", "TP. Đà Nẵng", "TP Đà Nẵng", "Da Nang", "Danang"],
    "thanhphohaiphong": ["Thành phố Hải Phòng", "Hải Phòng", "TP. Hải Phòng", "Hai Phong"],
    "thanhphocantho": ["Thành phố Cần Thơ", "Cần Thơ", "TP. Cần Thơ", "TP Cần Thơ"],
    "thanhphohue": ["Thành phố Huế", "Huế", "Thừa Thiên Huế", "TT Huế", "Thừa Thiên - Huế", "TP. Huế"],
    "tinhbariavungtau": ["Tỉnh Bà Rịa - Vũng Tàu", "Bà Rịa - Vũng Tàu", "Bà Rịa Vũng Tàu", "BR-VT", "BRVT",
                         "Ba Ria - Vung Tau"],
}
PREFIX_NOISE = [("", 88), ("Địa chỉ: ", 4), ("ĐC: ", 3), ("Đ/c: ", 1), ("Add: ", 1), ("Giao tới ", 1),
                ("Địa chỉ giao hàng: ", 2)]
SUFFIX_NOISE = [("", 80), (", Việt Nam", 7), (", VN", 3), (" Việt Nam", 2), (", Vietnam", 3), (" VN", 1),
                (", 700000", 1), (" 100000", 1), (", Viet Nam", 2)]


def wchoice(rng, items):
    vals, weights = zip(*items)
    return rng.choices(vals, weights=weights, k=1)[0]


def _typo(rng, s):
    letters = [i for i, ch in enumerate(s) if ch.isalpha()]
    if len(letters) < 4:
        return s
    i = rng.choice(letters[1:])
    op = rng.random()
    if op < 0.35:  # delete
        return s[:i] + s[i + 1:]
    if op < 0.6 and i + 1 < len(s) and s[i + 1].isalpha():  # swap
        return s[:i] + s[i + 1] + s[i] + s[i + 2:]
    if op < 0.8:  # duplicate
        return s[:i] + s[i] + s[i:]
    near = "qwertyuiopasdfghjklzxcvbnm"
    return s[:i] + rng.choice(near) + s[i + 1:]


class Generator:
    def __init__(self, gz: Gazetteer, seed: int = 0, typo_rate=0.08, noaccent_rate=0.35, profile="default"):
        self.gz = gz
        self.rng = random.Random(seed)
        self.typo_rate = typo_rate
        self.noaccent_rate = noaccent_rate
        self.profile = profile
        big = {"thanhphohanoi", "thanhphohochiminh", "thanhphodanang", "thanhphohaiphong", "thanhphocantho",
               "tinhbinhduong", "tinhdongnai"}
        self.old_units, w = [], []
        for (pk, dk), wards in gz.old_ward.items():
            for wk, u in (wards.items() if wards else [(None, None)]):
                self.old_units.append((pk, dk, wk))
                w.append((4.0 if pk in big else 1.0) * (1.6 if u and u.type in ("Phường", "Thị trấn") else 1.0))
        self.old_weights = w
        self.new_units, w = [], []
        for pk, wards in gz.new_ward.items():
            for wk, u in wards.items():
                self.new_units.append((pk, wk))
                w.append((4.0 if pk in big else 1.0) * (1.6 if u.type == "Phường" else 1.0))
        self.new_weights = w
        self.place_names = [short_name(u.name, DISTRICT_TYPES) for d in gz.old_dist.values() for u in d.values()
                            if not short_name(u.name, DISTRICT_TYPES).isdigit()] + [
            short_name(u.name, WARD_TYPES) for d in gz.old_ward.values() for u in d.values()]

    # ---------------- components ----------------
    def street(self, rural: bool):
        r = self.rng
        if r.random() < 0.08:
            return []
        parts = []
        n = r.choice([r.randint(1, 30), r.randint(1, 200), r.randint(1, 999)])
        if rural and r.random() < 0.6:
            kind = r.choice(["Thôn {v}", "Ấp {v}", "Xóm {n}", "Bản {v}", "Thôn {n}", "Ấp {n}", "Tổ {n}",
                             "Khóm {n}", "Tổ dân phố {n}", "Khu {n}", "Đội {n}", "thôn {v}", "ấp {v}"])
            parts.append(kind.format(v=r.choice(VILLAGE_NAMES), n=r.randint(1, 15)))
            if r.random() < 0.3:
                parts.insert(0, r.choice(["Số {n}", "{n}", "Nhà {n}"]).format(n=n))
            return parts
        house = r.choice(["{n}", "{n}", "{n}", "Số {n}", "số {n}", "{n}{a}", "{n}/{m}", "{n}/{m}/{k}", "SN {n}",
                          "Số nhà {n}", "{n}-{n2}", "Lô {A}{m}", "{n} bis", "Kiot {m}", "{n}B"])
        house = house.format(n=n, m=r.randint(1, 99), k=r.randint(1, 30), a=r.choice("ABCD"),
                             A=r.choice("ABCDE"), n2=n + 2)
        lane = ""
        x = r.random()
        if x < 0.12:
            lane = f"{r.choice(['Ngõ', 'ngõ', 'Ng.'])} {r.randint(1, 400)}"
            if r.random() < 0.4:
                lane += f" {r.choice(['Ngách', 'ngách'])} {r.randint(1, 80)}"
        elif x < 0.24:
            lane = f"{r.choice(['Hẻm', 'hẻm', 'Hẻm', 'H.'])} {r.randint(1, 500)}" + (
                f"/{r.randint(1, 60)}" if r.random() < 0.3 else "")
        elif x < 0.28:
            lane = f"{r.choice(['Kiệt', 'K'])} {r.randint(1, 300)}"
        name = r.choice(STREETS) if r.random() < 0.75 else r.choice(self.place_names)
        sp = r.choice(["Đường ", "", "", "", "đường ", "Đ. ", "Phố ", "phố ", "Đ.", "Duong "])
        if name.startswith(("Quốc lộ", "Tỉnh lộ", "Đại lộ", "Vành")):
            sp = ""
        st = f"{sp}{name}"
        if r.random() < 0.05:
            parts.append(r.choice([f"Tầng {r.randint(1, 30)}", f"Phòng {r.randint(101, 2505)}", "Block A",
                                   f"Tòa {r.choice('ABCDE')}{r.randint(1, 5)}"]))
            parts.append(r.choice(BUILDINGS))
        if lane:
            parts.append(f"{house} {lane}" if r.random() < 0.7 else house)
            if not lane in parts[-1]:
                parts.append(lane)
        else:
            parts.append(house)
        parts.append(st)
        if r.random() < 0.12:
            parts.append(r.choice([f"Khu phố {r.randint(1, 12)}", f"KP{r.randint(1, 9)}", f"Tổ {r.randint(1, 40)}",
                                   f"Tổ dân phố {r.randint(1, 30)}", f"KP.{r.randint(1, 9)}"]))
        # sometimes glue house + street into one chunk (most common way people type)
        if len(parts) >= 2 and r.random() < 0.75:
            parts = [" ".join(parts[:-1] if parts[-1].startswith(("Khu", "KP", "Tổ")) else parts)] + (
                [parts[-1]] if parts[-1].startswith(("Khu", "KP", "Tổ")) else [])
        return parts

    def fmt_ward(self, u):
        r = self.rng
        short = short_name(u.name, WARD_TYPES)
        if short.isdigit():
            return r.choice(WARD_NUM_VARIANTS).format(n=int(short), n0=f"{int(short):02d}")
        return wchoice(r, WARD_TYPE_VARIANTS[u.type]) + short

    def fmt_district(self, u):
        r = self.rng
        short = short_name(u.name, DISTRICT_TYPES)
        if short.isdigit():
            return r.choice(DIST_NUM_VARIANTS).format(n=int(short), n0=f"{int(short):02d}")
        if len(short.split()) >= 2 and u.type == "Quận" and r.random() < 0.06:  # "Q.BT" = Quận Bình Thạnh
            ini = "".join(w[0] for w in short.split()).upper()
            return r.choice(["Q.", "Q ", "Q."]) + (strip_accents(ini) if r.random() < 0.5 else ini)
        return wchoice(r, DIST_TYPE_VARIANTS[u.type]) + short

    def poi(self, pk, du, wu, pname):
        """Name of a place of interest, often containing admin names (a classic confounder)."""
        r = self.rng
        t = r.choice(POI_TEMPLATES)
        x = r.choice([r.choice(STREETS), r.choice(self.place_names), r.choice(VILLAGE_NAMES),
                      short_name(pname, ["Thành phố", "Tỉnh"])])
        ad = (du.name if du and r.random() < 0.6 else pname) if r.random() < 0.85 else r.choice(self.place_names)
        if r.random() < 0.3:
            ad = ad.replace("Thành phố", "TP").replace("Huyện", "huyện").replace("Tỉnh", "tỉnh")
        aw = wu.name if wu else x
        return t.format(X=x, AD=ad, AW=aw)

    def fmt_province(self, pk, name):
        r = self.rng
        if pk in PROVINCE_INITIALS and r.random() < 0.08:
            return r.choice(PROVINCE_INITIALS[pk])
        if pk in PROVINCE_SPECIAL and r.random() < 0.85:
            return r.choice(PROVINCE_SPECIAL[pk])
        short = name.split(" ", 1)[1] if name.startswith("Tỉnh ") else short_name(name, ["Thành phố"])
        if name.startswith("Tỉnh "):
            return wchoice(r, [("Tỉnh ", 30), ("", 55), ("T. ", 5), ("tỉnh ", 5), ("T.", 5)]) + short
        return wchoice(r, [("Thành phố ", 30), ("TP. ", 25), ("TP ", 15), ("", 30)]) + short

    # ---------------- sample ----------------
    def sample(self):
        r, gz = self.rng, self.gz
        fmt = "new" if r.random() < 0.4 else "old"
        segs = []  # (text, label or None) ; label None => O
        gold = {"fmt": fmt}
        if fmt == "old":
            pk, dk, wk = r.choices(self.old_units, weights=self.old_weights, k=1)[0]
            pu, du = gz.old_prov[pk], gz.old_dist[pk][dk]
            wu = gz.old_ward[(pk, dk)].get(wk) if wk else None
            rural = (wu is None) or wu.type == "Xã"
            has_w = wu is not None and r.random() > 0.04
            has_d = r.random() > (0.05 if has_w else 0.0)
            has_p = r.random() > 0.07
            comps = []
            if has_w:
                comps.append((self.fmt_ward(wu), "WARD"))
            if has_d:
                comps.append((self.fmt_district(du), "DISTRICT"))
            if has_p:
                comps.append((self.fmt_province(pk, pu.name), "PROVINCE"))
            gold["old"] = {"pk": pk, "dk": dk if has_d or has_w else None, "wk": wk if has_w else None}
            npk, cands = gz.convert(pk, dk, wk if has_w else None)
            gold["new_pk"] = npk
            gold["new_wards"] = [c[0] for c in cands] if has_w else []
            gold["new_default"] = next((c[0] for c in cands if c[1]), None) if has_w else None
        else:
            pk, wk = r.choices(self.new_units, weights=self.new_weights, k=1)[0]
            pu, wu = gz.new_prov[pk], gz.new_ward[pk][wk]
            rural = wu.type == "Xã"
            has_p = r.random() > 0.05
            comps = [(self.fmt_ward(wu), "WARD")]
            if has_p:
                comps.append((self.fmt_province(pk, pu.name), "PROVINCE"))
            gold.update({"old": None, "new_pk": pk, "new_wards": [wk], "new_default": wk})
        gold["has_province"] = has_p
        # ward mentioned only inside an institution name: "UBND xã Kim Chung, Đông Anh, HN"
        glue_ward = False
        if wu is not None and comps and comps[0][1] == "WARD" and r.random() < 0.07:
            short = short_name(wu.name, WARD_TYPES)
            tword = {"Phường": ["phường ", "Phường ", "P. ", "P."], "Xã": ["xã ", "Xã ", "X. "],
                     "Thị trấn": ["thị trấn ", "TT ", "TT. ", "Thị trấn "], "Đặc khu": ["đặc khu "]}[wu.type]
            comps[0] = (r.choice(tword) + short, "WARD")
            glue_ward = True
        street_parts = self.street(rural)
        if r.random() < 0.25:
            poi = self.poi(pk, du if fmt == "old" else None, wu, pu.name)
            if r.random() < 0.35 and street_parts:
                street_parts = [poi + " " + street_parts[0]] + street_parts[1:]
            else:
                street_parts = [poi] + street_parts
        gold["street"] = ", ".join(street_parts)
        if glue_ward:
            head = r.choice(["UBND", "Ủy ban nhân dân", "Công an", "Trạm y tế", "Trạm Y tế", "Trường THCS",
                             "Trường Tiểu học", "Bưu điện", "Hội trường", "Nhà văn hóa", "Chợ", "Đảng ủy"])
            street_parts = [] if r.random() < 0.7 else street_parts
            comps = [(s, "STREET") for s in street_parts] + [(head, "STREET")] + comps
        else:
            comps = [(s, "STREET") for s in street_parts] + comps
        if r.random() < 0.02 and len(comps) > 2:  # reversed order (province first)
            comps = comps[::-1]
        # typos on admin names
        if r.random() < self.typo_rate:
            idx = [i for i, (_, l) in enumerate(comps) if l in ("WARD", "DISTRICT", "PROVINCE")]
            if idx:
                i = r.choice(idx)
                comps[i] = (_typo(r, comps[i][0]), comps[i][1])
        # separators
        sep_mode = wchoice(r, SEPARATORS)
        pre = wchoice(r, PREFIX_NOISE)
        if pre:
            segs.append((pre, None))
        for i, (txt, lab) in enumerate(comps):
            if i and glue_ward and lab == "WARD" and comps[i - 1][1] == "STREET" and comps[i - 1][0] in (
                    "UBND", "Ủy ban nhân dân", "Công an", "Trạm y tế", "Trạm Y tế", "Trường THCS", "Trường Tiểu học",
                    "Bưu điện", "Hội trường", "Nhà văn hóa", "Chợ", "Đảng ủy"):
                segs.append((" ", None))
            elif i:
                segs.append((sep_mode if r.random() < 0.85 else wchoice(r, SEPARATORS), None))
            segs.append((txt, lab))
        suf = wchoice(r, SUFFIX_NOISE)
        if suf:
            segs.append((suf, None))
        # casing / accents
        accent_mode = r.random()
        case_mode = r.random()
        out = []
        for txt, lab in segs:
            if accent_mode < self.noaccent_rate or (accent_mode < self.noaccent_rate + 0.08 and r.random() < 0.5):
                txt = strip_accents(txt)
            if case_mode < 0.18:
                txt = txt.lower()
            elif case_mode < 0.23:
                txt = txt.upper()
            out.append((txt, lab))
        return self._encode(out, gold)

    @staticmethod
    def _encode(segs, gold):
        text, tokens, labels = "", [], []
        for txt, lab in segs:
            base = len(text)
            text += txt
            first = True
            for tok, s, e in tokenize(txt):
                tokens.append(tok)
                if lab is None or not tok.strip():
                    labels.append("O")
                else:
                    labels.append(("B-" if first else "I-") + lab)
                    first = False
        street = ", ".join(t.strip(" ,.-") for t, lab in segs if lab == "STREET")
        return {"text": text, "tokens": tokens, "labels": labels, **gold, "street": street}
