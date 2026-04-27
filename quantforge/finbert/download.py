"""CLI to pre-download FinBERT model."""


def main():
    print("Downloading ProsusAI/finbert model (~400MB)...")
    try:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        AutoTokenizer.from_pretrained("ProsusAI/finbert")
        AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
        print("FinBERT model downloaded successfully.")
    except Exception as e:
        print(f"Download failed: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
