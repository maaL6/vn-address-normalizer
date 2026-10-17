# Development history

Numbers from intermediate runs that are no longer reproducible with the current code. The resolver kept changing, and the synthetic test sets were regenerated whenever the generator changed. All values are ward accuracy (%). The final numbers are in `results.json`.

## v1 tagger (addresses only, no place names in front)

| Set | v1 model | rule-based library |
|---|---|---|
| synthetic test (first 1,000) | 98.3 | 90.1 |
| synthetic hard (first 1,000) | 98.0 | 75.7 |
| dev_real (266) | 79.7 | 92.1 |

Most dev_real errors came from addresses that start with a place name ("Chợ Bến Thành, …", "BV đa khoa tỉnh …"). The generator never produced those.

## v2 tagger (+ place names, province initials)

- **dev_real:** 97.7. After fixing two resolver bugs found on this set ("Phương Mai" read as "Phường Mai"; districts dissolved before 2025), it reached 100. That 100 says more about tuning to the set than about the system.
- **First held-out set, now `dev2_real`:** 88.9, against 89.8 for the rule-based library (DistilBERT v2: 90.7). 18 of the 25 errors were wards that appear only inside an institution name ("UBND xã X, huyện Y").
- **Resolver fix for wards inside institution names:** `dev2_real` went to 96.4. From then on the set was treated as a second dev set.

## v3 tagger (+ wards inside institution names), model selection

Selection used only the dev sets. `val` is the synthetic validation split from the v3 generator, so it slightly favours v3.

| Model | val | dev_real | dev2_real | mean |
|---|---|---|---|---|
| XLM-R v2 | 97.7 | 99.2 | 96.4 | 97.8 |
| DistilBERT v2 | 97.3 | 97.7 | 96.4 | 97.2 |
| **XLM-R v3** | 98.1 | 98.1 | 97.8 | **98.0** |
| DistilBERT v3 | 98.0 | 98.1 | 96.9 | 97.7 |

XLM-R v3 was chosen. After that, `final_real` was written and every system was evaluated on it once (`final_eval.log`).
