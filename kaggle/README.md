# Training on Kaggle

`train_tagger.py` is a self-contained GPU job written as a plain PyTorch loop, without `Trainer`. It reads `train/val/test/test_hard.jsonl` from whichever dataset is attached and writes one folder per model to `/kaggle/working`.

```bash
.venv/bin/python scripts/gen_data.py          # ~2 min, ~130 MB in data/synth/
mkdir -p kaggle/build/data kaggle/build/kernel
cp data/synth/*.jsonl kaggle/build/data/
cp kaggle/dataset-metadata.example.json kaggle/build/data/dataset-metadata.json   # put your username in it
cp kaggle/train_tagger.py kaggle/build/kernel/
cp kaggle/kernel-metadata.example.json kaggle/build/kernel/kernel-metadata.json  # same here

kaggle datasets create -p kaggle/build/data
kaggle kernels push -p kaggle/build/kernel
kaggle kernels output <your-kaggle-username>/vn-address-tagger-train -p kaggle/output
cp -r kaggle/output/xlmr-base models/tagger
```

The models and hyperparameters are listed in `MODELS` at the top of the script. You can also override them with the `MODELS` environment variable when running locally with `DATA_DIR=... OUT_DIR=...`. On a T4, XLM-R takes about 25 minutes and DistilBERT about 12.
