# Dataset

[IEEE-CIS Fraud Detection](https://www.kaggle.com/competitions/ieee-fraud-detection/data)
(Kaggle competition data). Not committed to the repo — download it yourself:

```bash
# requires a Kaggle account + API token in ~/.kaggle/kaggle.json
kaggle competitions download -c ieee-fraud-detection -p data/raw
cd data/raw && unzip ieee-fraud-detection.zip
```

Files used: `train_transaction.csv`, `train_identity.csv` (~590K transactions,
identity data joins on `TransactionID`, ~3.5% labeled fraud via `isFraud`).

`download.py` checks the files exist and reports row counts / fraud rate as a
sanity check before ingestion.
