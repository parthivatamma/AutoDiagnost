import argparse
import pickle
from pathlib import Path

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

FEATURE_COLUMNS = [
    "RPM",
    "Engine_Load_pct",
    "Short_Term_Fuel_Trim_pct",
    "Long_Term_Fuel_Trim_pct",
    "MAF_g_s",
]
TARGET_COLUMN = "Failure_Mode"
DEFAULT_DATASET = Path("auto_diagnost_mock_data.csv")
DEFAULT_MODEL = Path("auto_diagnost_model.pkl")
RANDOM_STATE = 42


def load_dataset(dataset_path: Path) -> tuple[pd.DataFrame, pd.Series]:
    """Load and validate the telemetry features and diagnosis labels."""
    if not dataset_path.is_file():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    data = pd.read_csv(dataset_path)
    required_columns = [*FEATURE_COLUMNS, TARGET_COLUMN]
    missing_columns = [
        column for column in required_columns if column not in data.columns
    ]
    if missing_columns:
        raise ValueError(
            f"Dataset is missing required columns: {', '.join(missing_columns)}"
        )

    if data.empty:
        raise ValueError("Dataset contains no rows.")

    features = data[FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    invalid_feature_rows = features.isna().any(axis=1)
    if invalid_feature_rows.any():
        raise ValueError(
            f"Dataset contains invalid or missing telemetry values in "
            f"{invalid_feature_rows.sum()} row(s)."
        )

    labels = data[TARGET_COLUMN]
    if labels.isna().any() or labels.astype(str).str.strip().eq("").any():
        raise ValueError("Dataset contains missing or empty diagnosis labels.")
    if labels.nunique() < 2:
        raise ValueError("Dataset must contain at least two diagnosis classes.")

    return features, labels


def train_model(
    features: pd.DataFrame,
    labels: pd.Series,
) -> tuple[RandomForestClassifier, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Train a reproducible random forest and return its evaluation split."""
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=0.2,
        random_state=RANDOM_STATE,
        stratify=labels,
    )

    classifier = RandomForestClassifier(
        n_estimators=200,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    classifier.fit(x_train, y_train)
    return classifier, x_train, x_test, y_train, y_test


def save_model(model_path: Path, classifier: RandomForestClassifier) -> None:
    """Persist the classifier and feature schema for the inference step."""
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_bundle = {
        "model": classifier,
        "feature_columns": FEATURE_COLUMNS,
        "target_column": TARGET_COLUMN,
    }
    with model_path.open("wb") as model_file:
        pickle.dump(model_bundle, model_file)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the AutoDiagnost Random Forest classifier."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help=f"Input CSV path (default: {DEFAULT_DATASET})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_MODEL,
        help=f"Output model path (default: {DEFAULT_MODEL})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    features, labels = load_dataset(args.dataset)
    classifier, _, x_test, _, y_test = train_model(features, labels)

    predictions = classifier.predict(x_test)
    print(f"Accuracy: {accuracy_score(y_test, predictions):.3f}")
    print("\nClassification report:")
    print(classification_report(y_test, predictions, zero_division=0))

    save_model(args.output, classifier)
    print(f"Saved trained model to: {args.output.resolve()}")


if __name__ == "__main__":
    main()
