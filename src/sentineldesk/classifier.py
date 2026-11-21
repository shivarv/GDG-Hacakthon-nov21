"""Multi-task triage classifier: shared TF-IDF features, one calibrated linear model per target."""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion
from sklearn.svm import LinearSVC

from .data import TARGETS


class TriageClassifier:
    def __init__(self, targets: list[str] | None = None):
        self.targets = targets or list(TARGETS)
        self.features = FeatureUnion([
            ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=200_000,
                                     sublinear_tf=True, strip_accents=None)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3,
                                     max_features=200_000, sublinear_tf=True)),
        ])
        self.models: dict[str, CalibratedClassifierCV] = {}

    def fit(self, texts: list[str], labels: dict[str, list[str]], verbose: bool = True):
        X = self.features.fit_transform(texts)
        for t in self.targets:
            if verbose:
                print(f"  training '{t}' on {X.shape[0]:,} docs x {X.shape[1]:,} features")
            model = CalibratedClassifierCV(
                LinearSVC(C=0.5, class_weight="balanced"), method="sigmoid", cv=3
            )
            model.fit(X, labels[t])
            self.models[t] = model
        return self

    def predict_proba(self, texts: list[str]) -> dict[str, tuple[np.ndarray, np.ndarray]]:
        """Returns {target: (classes, probability matrix)}."""
        X = self.features.transform(texts)
        return {t: (m.classes_, m.predict_proba(X)) for t, m in self.models.items()}

    def predict(self, texts: list[str]) -> list[dict]:
        out = [dict() for _ in texts]
        for t, (classes, P) in self.predict_proba(texts).items():
            for i, row in enumerate(P):
                j = int(row.argmax())
                out[i][t] = {
                    "label": str(classes[j]),
                    "confidence": float(row[j]),
                    "probs": {str(c): float(p) for c, p in zip(classes, row)},
                }
        return out

    def predict_one(self, text: str) -> dict:
        return self.predict([text])[0]

    def save(self, path: str | Path):
        joblib.dump({"targets": self.targets, "features": self.features, "models": self.models}, path)

    @classmethod
    def load(cls, path: str | Path) -> "TriageClassifier":
        blob = joblib.load(path)
        obj = cls(blob["targets"])
        obj.features, obj.models = blob["features"], blob["models"]
        return obj
