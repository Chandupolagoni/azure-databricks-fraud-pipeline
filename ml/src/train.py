"""Trains a gradient-boosted fraud classifier on the Gold feature set, tracks the run
with MLflow, and registers the model if it clears the promotion gate.

Usage:
    python ml/src/train.py --delta-path <path> --labels-path <path>
    python ml/src/train.py --synthetic          # runs against generated sample data
"""

import argparse

import mlflow
import mlflow.sklearn
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split

from feature_store import FEATURE_COLUMNS, LABEL_COLUMN, load_training_frame, make_synthetic_training_frame
from evaluate import evaluate_predictions

MODEL_NAME = "fraud-risk-classifier"
PROMOTION_AUC_PR_THRESHOLD = 0.55


def train(delta_path: str | None, labels_path: str | None, use_synthetic: bool) -> None:
    df = (
        make_synthetic_training_frame()
        if use_synthetic
        else load_training_frame(delta_path, labels_path)
    )

    X_train, X_test, y_train, y_test = train_test_split(
        df[FEATURE_COLUMNS], df[LABEL_COLUMN], test_size=0.2, stratify=df[LABEL_COLUMN], random_state=42
    )

    params = {
        "n_estimators": 300,
        "max_depth": 4,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "random_state": 42,
    }

    with mlflow.start_run(run_name="fraud-gbm-training") as run:
        mlflow.log_params(params)

        model = GradientBoostingClassifier(**params)
        model.fit(X_train, y_train)

        y_proba = model.predict_proba(X_test)[:, 1]
        metrics = evaluate_predictions(y_test, y_proba)
        mlflow.log_metrics(metrics)

        mlflow.sklearn.log_model(model, artifact_path="model", registered_model_name=MODEL_NAME)

        print(f"Run {run.info.run_id} — metrics: {metrics}")

        if metrics["auc_pr"] >= PROMOTION_AUC_PR_THRESHOLD:
            client = mlflow.tracking.MlflowClient()
            latest = client.get_latest_versions(MODEL_NAME, stages=["None"])[0]
            client.transition_model_version_stage(
                name=MODEL_NAME, version=latest.version, stage="Staging"
            )
            print(f"Model version {latest.version} promoted to Staging (auc_pr={metrics['auc_pr']:.3f})")
        else:
            print(f"Model did not clear promotion gate (auc_pr={metrics['auc_pr']:.3f} < {PROMOTION_AUC_PR_THRESHOLD})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--delta-path", default=None)
    parser.add_argument("--labels-path", default=None)
    parser.add_argument("--synthetic", action="store_true")
    args = parser.parse_args()

    train(args.delta_path, args.labels_path, args.synthetic)
