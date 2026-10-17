# fp32 vs dynamic int8 (xlmr-base, 512 addresses from test_hard.jsonl, CPU)

| | ms/address (batch 64) | ms/address (one at a time) | tag sequence accuracy |
|---|---|---|---|
| fp32 | 37.9 | 41.5 | 94.7% |
| int8 | 27.4 | 27.9 | 86.5% |
