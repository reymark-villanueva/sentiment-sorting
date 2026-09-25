"""
Isabela State University - Cauayan Campus Library
Trained Sentiment Classification Model — Loading & Inference

`sentiment_model.pkl` and `vectorizer.pkl` were produced by
`sentiment_sorting_merged_library_V2.ipynb` via joblib.dump(). The `Hybrid`
class and `preprocess()` function below must match that notebook exactly:
joblib/pickle resolve a custom class by import path (`feedback.ml.Hybrid`),
not by copying its code into the pickle, so this file has to define the
identical class for `joblib.load()` to reconstruct the model.
"""

import re
import sys

import joblib
from django.conf import settings
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.naive_bayes import MultinomialNB
from sklearn.tree import DecisionTreeClassifier

# Mirrors the notebook's SENTIMENT_PRIORITY mapping (negative sorts first).
SENTIMENT_PRIORITY = {'negative': 0, 'neutral': 1, 'positive': 2}


class Hybrid(BaseEstimator, ClassifierMixin):
    """Naive Bayes primary classifier with a Decision Tree fallback for low-confidence predictions."""

    def __init__(self, threshold=0.9):
        self.threshold = threshold

    def fit(self, X, y):
        self.nb_ = MultinomialNB(alpha=0.3).fit(X, y)
        self.dt_ = DecisionTreeClassifier(
            class_weight='balanced', min_samples_leaf=2, random_state=42
        ).fit(X, y)
        return self

    def predict(self, X):
        proba = self.nb_.predict_proba(X)
        pred = self.nb_.predict(X).copy()
        low_confidence = proba.max(axis=1) < self.threshold
        if low_confidence.any():
            pred[low_confidence] = self.dt_.predict(X[low_confidence])
        return pred


def preprocess(text):
    """Must match the cleaning applied to training text exactly (see notebook cell 4)."""
    text = re.sub(r'[^a-zA-Z\s]', ' ', str(text).lower())
    return ' '.join(text.split())


# `sentiment_model.pkl` was saved from a Jupyter notebook, where `Hybrid` was defined
# in the `__main__` namespace — so the pickle references `__main__.Hybrid`, not
# `feedback.ml.Hybrid`. Register it under `__main__` too so joblib.load() can resolve
# it no matter which script (manage.py, a WSGI server, ...) is actually running.
sys.modules['__main__'].Hybrid = Hybrid


_model = None
_vectorizer = None


def _load():
    """Lazily load and cache the model + vectorizer (loaded once per process)."""
    global _model, _vectorizer
    if _model is None or _vectorizer is None:
        _model = joblib.load(settings.BASE_DIR / 'sentiment_model.pkl')
        _vectorizer = joblib.load(settings.BASE_DIR / 'vectorizer.pkl')
    return _model, _vectorizer


def classify(text):
    """Predict a sentiment label ('negative' / 'neutral' / 'positive') for free text."""
    model, vectorizer = _load()
    cleaned = preprocess(text)
    features = vectorizer.transform([cleaned])
    label = model.predict(features)[0]
    return str(label).lower()
