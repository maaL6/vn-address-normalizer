# Real-style evaluation sets

Three sets of addresses for real places (hospitals, schools, UBND offices, shops, homes), written
the way people type them into delivery forms: with or without accents, abbreviations, missing
separators, typos, place names in front. An LLM wrote them in batches, one region
at a time. `scripts/build_real_eval.py` then checks every gold unit against the pre-2025 gazetteer
and drops any row where a unit doesn't exist. All addresses are in the old (pre-1/7/2025) format.

| File | Rows | Role |
|---|---|---|
| `dev_real.jsonl` | 266 | error analysis during development |
| `dev2_real.jsonl` | 225 | first held-out test; became a second dev set after its first run |
| `final_real.jsonl` | 224 | written after all design decisions, evaluated once |

Fields: `text` (input), `old` (gold old unit keys), `new_pk` / `new_wards` / `new_default`
(gold new unit; several wards when the old ward was split), `street`, `place`, `confidence`,
`relabelled_from_historic_name` (the text uses a name from before a 2019–2025 merger).

The gold label is the unit written in the text, not a geocoded location. These are not production
logs, so treat the numbers as an estimate.
