# vn-address-normalizer

[English](README.md)

Từ 1/7/2025, cả nước gộp từ 63 tỉnh/thành xuống còn 34 và bỏ hẳn cấp huyện. Địa chỉ trong dữ liệu khách hàng, lịch sử đơn hàng hay hệ thống giao vận giờ phần lớn đang ghi theo những đơn vị hành chính không còn nữa. Đó là chưa kể người dùng vốn đã chẳng bao giờ gõ địa chỉ cho tử tế: `12 ng trai p.ben thanh q1 tphcm`.

Project này nhận địa chỉ đúng kiểu người ta hay gõ, xác định đó là phường, quận, tỉnh nào, rồi trả lại địa chỉ theo hệ 2 cấp mới.

```
$ vnaddr "Số 1 Đại Cồ Việt p bach khoa q hai ba trung hn"
old: Phường Bách Khoa, Quận Hai Bà Trưng, Thành phố Hà Nội
new: Số 1 Đại Cồ Việt, Phường Bạch Mai, Thành phố Hà Nội
confidence: 1.0
```

![Web demo](docs/demo.png)

Hệ thống nhận được cả địa chỉ kiểu cũ (phường, quận, tỉnh) lẫn kiểu mới, và cho biết nó thấy kiểu nào. Nếu phường cũ đã bị chia cho nhiều phường mới, nó trả về phường mặc định theo nghị quyết kèm các phương án còn lại, chứ không đoán bừa.

## Kết quả

Thước đo mình dùng là độ chính xác ở cấp phường: có ra đúng phường mới và tỉnh mới hay không.

| | Synthetic | Synthetic khó | Bộ test sát thực tế |
|---|---|---|---|
| [vietnamadminunits](https://github.com/tranngocminhhieu/vietnamadminunits) (thư viện dùng luật) | 89,3% | 75,2% | 86,6% |
| Tách bằng luật + resolver của mình | 75,6% | 73,1% | 84,8% |
| **XLM-R fine-tune + resolver của mình** | **98,7%** | **98,0%** | **99,6%** (223/224) |

Bộ synthetic (5.000 địa chỉ) lấy từ bộ sinh dữ liệu với seed chưa dùng khi train; bản khó (3.000 địa chỉ) có 35% địa chỉ gõ sai và 70% không dấu. Bộ test sát thực tế gồm 224 địa chỉ của các địa điểm có thật (nhà riêng, cửa hàng, trường học, bệnh viện, UBND), viết theo cách người ta điền form giao hàng. Mình tạo bộ này sau khi đã chốt hết các quyết định thiết kế, và chỉ chạy nó đúng một lần.

`vietnamadminunits` được chạy offline giống hệ thống của mình, và mình báo trước cho nó biết mỗi địa chỉ là kiểu cũ hay mới vì nó không tự nhận ra được, tức là đang có lợi cho nó. Bù lại nó nhanh hơn hẳn: 1–3 ms một địa chỉ, còn của mình mất 55–80 ms trên CPU laptop.

Các bộ test sát thực tế do LLM viết, và mình đã đối chiếu từng nhãn với danh mục đơn vị hành chính chính thức; chi tiết trong [data/eval/README.md](data/eval/README.md). Đây không phải dữ liệu production, nên chạy trên dữ liệu khách hàng thật thì nhiều khả năng con số sẽ thấp hơn.

## Cách hoạt động

Có hai bước.

**1. Tách địa chỉ thành từng phần.** Một model `xlm-roberta-base` (277 triệu tham số) được fine-tune để gán nhãn từng từ: chi tiết số nhà/đường, phường, quận hay tỉnh. Làm bước này bằng luật thì nhanh chóng chạm giới hạn: dấu phẩy có cũng được không có cũng được, `P.` có khi là "phường" có khi là một phần của tên, và rất nhiều địa chỉ mở đầu bằng kiểu "BV đa khoa tỉnh Bình Dương", trong đó có tên một tỉnh nhưng không phải tỉnh của địa chỉ. Lỗi chủ yếu nằm ở bước này: nếu tách đúng hoàn toàn thì phần còn lại đạt 98,8% trên bộ synthetic, còn tách bằng luật thì chỉ được 75,6%.

**2. Tra cứu và chuyển đổi.** Từng phần được so với 10.040 đơn vị cũ và 3.321 đơn vị mới. Bước so khớp xử lý được viết tắt (`P.`, `F.`, `Q1`, `TX.`, `TT.`), gõ sai, mất dấu, tên trùng đầu với tiền tố ("Phương Mai" chứ không phải "Phường Mai"), cách gọi tắt tên tỉnh (`SG`, `HN`, `BRVT`, và `ĐN` có thể là hai tỉnh khác nhau) và tên từ các đợt sáp nhập từ 2019 đến đầu 2025. Hệ thống chấm điểm song song cả hai cách đọc theo kiểu cũ và kiểu mới. Khi tên tỉnh có vẻ sai, nó tìm trên cả nước; khi không có phần nào được gán nhãn phường, nó tìm phường nằm trong tên cơ quan ("UBND xã Kim Chung, Đông Anh, HN"). Kết quả sau đó được chuyển theo bảng cũ → mới chính thức, phủ toàn bộ đơn vị cũ.

Danh mục đơn vị và bảng chuyển đổi lấy từ package [vietnamadminunits](https://github.com/tranngocminhhieu/vietnamadminunits) (MIT); `scripts/build_gazetteer.py` chuyển chúng thành `data/gazetteer.json`.

### Dữ liệu train

Chưa có bộ dữ liệu công khai nào về địa chỉ tiếng Việt "bẩn" có gán nhãn, nên mình viết bộ sinh dữ liệu (`src/vnaddr/synth.py`) và train trên 200 nghìn địa chỉ do nó tạo ra. Bộ sinh bỏ dấu, viết hoa thường lộn xộn, dùng cả chục cách viết cho mỗi loại đơn vị, bỏ hoặc đổi dấu phân cách, thêm lỗi gõ, ngõ/ngách/hẻm/kiệt, thôn/ấp/tổ, tên tòa nhà, và đặt tên cửa hàng, cơ quan ở đầu địa chỉ.

Train trên GPU T4 miễn phí của Kaggle: khoảng 25 phút với XLM-R và 12 phút với DistilBERT (`kaggle/train_tagger.py`).

## Những lần vấp

Model đầu tiên đạt 98% trên dữ liệu synthetic nhưng chỉ khoảng 80% trên bộ dev sát thực tế. Địa chỉ thật hay mở đầu bằng tên địa điểm ("Chợ Bến Thành, …", "BV đa khoa tỉnh Vĩnh Phúc, …"), bộ sinh của mình chưa tạo ra kiểu này bao giờ, thế là model gán luôn tên bệnh viện thành tỉnh. Thêm tên địa điểm vào bộ sinh thì sửa được phần lớn.

Sau đó mình thử trên một bộ sát thực tế mới và chỉ được 88,9%, thấp hơn một chút so với thư viện dùng luật trên cùng bộ đó (89,8%). Mình đã chỉnh resolver trên bộ dev tới mức nhìn rất đẹp, nhưng sang bộ mới thì không còn giữ được. 18 trong 25 lỗi có chung một dạng: "UBND xã X, huyện Y" hay "Công an phường X, quận Y", tức là phường chỉ xuất hiện trong tên cơ quan. Mình sửa cả ở resolver lẫn bộ sinh dữ liệu. Vì đã xem lỗi của bộ đó rồi, mình chuyển nó thành bộ dev thứ hai và viết thêm bộ thứ ba để lấy con số cuối. Các con số trung gian nằm trong [reports/history.md](reports/history.md).

Ảnh hưởng của từng thay đổi trong dữ liệu train, đo với cùng một resolver trên bộ test cuối:

| Model | Dữ liệu train | Bộ test sát thực tế |
|---|---|---|
| XLM-R v1 | chỉ có địa chỉ | 83,9% |
| XLM-R v2 | + tên địa điểm đứng trước, viết tắt tên tỉnh | 98,7% |
| XLM-R v3 | + phường nằm trong tên cơ quan | 99,6% |
| DistilBERT-multilingual v3 (135 triệu tham số) | giống v3 | 99,6% |

DistilBERT nhanh khoảng gấp đôi và gần ngang XLM-R trên bộ synthetic (98,6% và 97,9%), nên đáng cân nhắc nếu cần tốc độ.

Kết quả chính, kể cả trên các bộ dev, nằm trong `reports/results.json`. Kết quả từng phiên bản trong bảng trên nằm ở `reports/results_v*.json`, còn các lỗi còn lại ở `reports/errors/`.

## Chạy thử

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[model]"     # hoặc chỉ -e . nếu chỉ cần bộ tách bằng luật, không cần torch
```

Model không nằm trong repo. Hãy đặt một tagger đã train vào `models/tagger/`, xem hướng dẫn trong [models/README.md](models/README.md). Không có model thì mọi thứ vẫn chạy bằng bộ tách bằng luật, kém hơn nhiều, và CLI sẽ in cảnh báo.

```bash
# một địa chỉ (thêm --json để xem kết quả đầy đủ)
.venv/bin/vnaddr "12 ng trai p.ben thanh q1 tphcm"

# một file CSV: thêm các cột vnaddr_* bên cạnh cột của bạn
.venv/bin/vnaddr --csv customers.csv --column address --out customers_2025.csv

# HTTP API + web demo tại http://localhost:8000
.venv/bin/uvicorn vnaddr.api:app --port 8000
curl -s localhost:8000/normalize -H 'Content-Type: application/json' -d '{"address": "Q.BT, P.25, SG"}'

# Docker (thư mục models/ được copy vào image)
docker build -t vnaddr . && docker run -p 8000:8000 vnaddr
```

`POST /normalize` nhận `{"address": "..."}`, `POST /normalize/batch` nhận `{"addresses": [...]}` (tối đa 1.000), còn `GET /health` cho biết đang dùng tagger nào. Kết quả gồm:

- `new`: tỉnh, phường và địa chỉ mới đầy đủ
- `old`: phường, quận, tỉnh cũ, khi đầu vào là kiểu cũ
- `fmt`: `old` hay `new`, tùy đầu vào trông như kiểu nào
- `split_ward` / `alternatives`: phường cũ có bị chia hay không, và nếu có thì các phường mới có thể
- `confidence`: từ 0 đến 1. Khi chuyển đổi hàng loạt, mình sẽ đưa những dòng dưới khoảng 0,7 sang kiểm tra tay.
- `spans`, `street`: địa chỉ đã được tách ra thế nào

### Tái tạo kết quả

```bash
.venv/bin/pip install -e ".[model,dev]"
.venv/bin/python scripts/gen_data.py      # ~2 phút, ~130 MB trong data/synth/
# train trên Kaggle (xem kaggle/README.md) rồi copy model vào models/tagger/
.venv/bin/python scripts/evaluate.py --out reports/results.json --errors reports/errors
.venv/bin/python scripts/make_report.py
.venv/bin/python -m pytest -q
```

Nếu chưa có model trong `models/tagger/`, `evaluate.py` sẽ bỏ qua các dòng của model (và có báo), nên file kết quả chỉ còn các baseline.

## Hạn chế

- 471 phường cũ bị chia cho nhiều phường mới. Muốn chọn đúng phải biết vị trí căn nhà, nên khi không có geocoding thì hệ thống trả về phường mặc định kèm danh sách.
- "P.5" chưa khớp được với những phường có tên chính thức là "Phường V". Đây là lỗi duy nhất trên bộ test cuối.
- Tên đơn vị cũ hơn lịch sử sáp nhập có trong danh mục thì không tra được.
- Lượng tử hóa int8 động giúp model nhanh hơn khoảng 1,4 lần trên CPU nhưng giảm 8 điểm độ chính xác gán nhãn ([reports/int8_check.md](reports/int8_check.md)), nên mặc định đang tắt.

## Cấu trúc thư mục

```
src/vnaddr/     text, gazetteer, synth (bộ sinh dữ liệu), tagger, resolver, pipeline, api, CLI
scripts/        build_gazetteer, gen_data, evaluate, make_report, build_real_eval, int8_check
kaggle/         job train trên GPU + mẫu metadata
data/           gazetteer.json, eval/ (các bộ test sát thực tế)
reports/        kết quả, lỗi theo từng bộ, metrics train, lịch sử
web/ docs/ tests/
```

## Giấy phép

MIT. Dữ liệu đơn vị hành chính lấy từ [vietnamadminunits](https://github.com/tranngocminhhieu/vietnamadminunits) (MIT).
