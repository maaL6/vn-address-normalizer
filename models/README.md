# Models

Trained taggers aren't stored in git: the XLM-R checkpoint is about 550 MB in fp16.

The code looks for a tagger in `models/tagger/`, or wherever `VNADDR_MODEL` points. The folder needs the usual Hugging Face files: `config.json`, `model.safetensors`, `tokenizer.json` and `tokenizer_config.json`. Without a model, the pipeline falls back to the rule-based splitter, which is much less accurate (see the results table in the main README).

To get one, train it with `kaggle/train_tagger.py` (about 25 minutes for XLM-R on a free Kaggle T4; see `kaggle/README.md`), then copy the output folder here:

```bash
cp -r kaggle/output/xlmr-base models/tagger      # or: export VNADDR_MODEL=kaggle/output/xlmr-base
```

Training metrics for the runs reported in the README are in `reports/training_metrics.json`.
