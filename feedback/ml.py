"""
Isabela State University - Cauayan Campus Library
Trained Sentiment Classification Model — Loading & Inference

`sentiment_model.pkl` and `vectorizer.pkl` were produced by
`v7 model/sentiment_sorting_LFS_V7.ipynb` (trained on `LFS v6 DATA.csv`) via joblib.dump(). The `Hybrid`
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
from sklearn.calibration import CalibratedClassifierCV
from sklearn.naive_bayes import MultinomialNB
from sklearn.tree import DecisionTreeClassifier

# Mirrors the notebook's SENTIMENT_PRIORITY mapping (negative sorts first).
SENTIMENT_PRIORITY = {'negative': 0, 'neutral': 1, 'positive': 2}


class Hybrid(BaseEstimator, ClassifierMixin):
    """Naive Bayes primary classifier with a Decision Tree fallback for low-confidence predictions.

    Naive Bayes is probability-calibrated (so its confidence is meaningful) and the tree needs
    `min_samples_leaf` rows per leaf (so its leaves are not all pure). Only predict() runs in the
    app; fit() mirrors the notebook so this class stays an exact copy of it.
    """

    def __init__(self, threshold=0.9, nb_alpha=0.3, calibration=None, max_depth=None, min_samples_leaf=2):
        self.threshold = threshold
        self.nb_alpha = nb_alpha
        self.calibration = calibration
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf

    def fit(self, X, y):
        nb = MultinomialNB(alpha=self.nb_alpha)
        self.nb_ = nb if self.calibration is None else CalibratedClassifierCV(nb, method=self.calibration, cv=5)
        self.nb_.fit(X, y)
        self.dt_ = DecisionTreeClassifier(
            class_weight='balanced', max_depth=self.max_depth,
            min_samples_leaf=self.min_samples_leaf, random_state=42,
        ).fit(X, y)
        return self

    def predict(self, X):
        proba = self.nb_.predict_proba(X)
        pred = self.nb_.predict(X).copy()
        low_confidence = proba.max(axis=1) < self.threshold
        if low_confidence.any():
            pred[low_confidence] = self.dt_.predict(X[low_confidence])
        return pred


# Words that flip the meaning of what follows (English and Tagalog). After one of these, the next
# NEGATION_WINDOW words of the same clause are preceded by a `neg` token.
NEGATORS = {'not', 'no', 'never', 'none', 'nothing', 'nobody', 'without', 'cannot', 'hardly',
            'hindi', 'di', 'walang', 'wala', 'ayaw', 'huwag', 'wag'}
NEGATION_WINDOW = 3

# Common short forms and Tagalog spelling variants mapped to one spelling.
SLANG = {'u': 'you', 'ur': 'your', 'pls': 'please', 'plz': 'please', 'thx': 'thanks', 'tnx': 'thanks',
         'ty': 'thank you', 'ok': 'okay', 'okey': 'okay', 'di': 'hindi', 'wag': 'huwag', 'ung': 'yung',
         'yun': 'yung', 'tlga': 'talaga', 'talga': 'talaga', 'nmn': 'naman', 'nman': 'naman', 'lng': 'lang',
         'sna': 'sana', 'bkt': 'bakit', 'sobrang': 'sobra', 'dun': 'doon'}


def _normalize_slang(text):
    text = re.sub(r'wi[\s\-]?fi', 'wifi', text)                       # wi-fi / wi fi / wifi -> wifi
    return re.sub(r"[a-z']+", lambda m: SLANG.get(m.group(0), m.group(0)), text)


def _expand_contractions(text):
    text = text.replace('\u2019', "'")
    text = re.sub(r"won't", 'will not', text)
    text = re.sub(r"can't", 'can not', text)
    return re.sub(r"n't\b", ' not', text)                                # don't -> do not


def _mark_negation(text):
    """Put a `neg` token before each of the NEGATION_WINDOW words after a negator, within one clause."""
    out = []
    for clause in re.split(r'[.,;:!?\n]+', text):
        left = 0
        for w in re.findall(r"[a-z']+", clause):
            if w in NEGATORS:
                left = NEGATION_WINDOW
                out.append(w)
            elif left > 0:
                out.extend(['neg', w])
                left -= 1
            else:
                out.append(w)
    return ' '.join(out)


def preprocess(text):
    """Must match the cleaning applied to training text exactly (see the notebook's preprocessing cell).

    Lowercase -> slang / spelling normalization -> contraction expansion -> negation marking -> keep letters only.
    """
    text = _mark_negation(_expand_contractions(_normalize_slang(str(text).lower())))
    text = re.sub(r'[^a-zA-Z\s]', ' ', text)
    return ' '.join(text.split())


# `sentiment_model.pkl` was saved from a Jupyter notebook, where `Hybrid` was defined
# in the `__main__` namespace — so the pickle references `__main__.Hybrid`, not
# `feedback.ml.Hybrid`. Register it under `__main__` too so joblib.load() can resolve
# it no matter which script (manage.py, a WSGI server, ...) is actually running.
sys.modules['__main__'].Hybrid = Hybrid


MODEL_FILE = 'sentiment_model.pkl'
VECTORIZER_FILE = 'vectorizer.pkl'

_model = None
_vectorizer = None
_loaded_mtimes = None


class ModelUnavailable(RuntimeError):
    """The trained model or vectorizer file is missing, so nothing can be classified."""


def _file_mtimes():
    """Modification times of the model + vectorizer files.

    Raises ModelUnavailable if either file is missing, so callers can handle that
    one case instead of catching a bare FileNotFoundError.
    """
    try:
        return tuple((settings.BASE_DIR / name).stat().st_mtime_ns for name in (MODEL_FILE, VECTORIZER_FILE))
    except FileNotFoundError as exc:
        raise ModelUnavailable(
            f"Sentiment model files not found ({MODEL_FILE}, {VECTORIZER_FILE}) in {settings.BASE_DIR}."
        ) from exc


def _load():
    """Load and cache the model + vectorizer, reloading them whenever the .pkl files change.

    Without the mtime check, a retrained model dropped into the project would be
    ignored until the server restarted (runserver only restarts on .py changes),
    so new feedback would silently keep being classified by the old model.
    """
    global _model, _vectorizer, _loaded_mtimes
    mtimes = _file_mtimes()
    if _model is None or _vectorizer is None or mtimes != _loaded_mtimes:
        _model = joblib.load(settings.BASE_DIR / MODEL_FILE)
        _vectorizer = joblib.load(settings.BASE_DIR / VECTORIZER_FILE)
        _loaded_mtimes = mtimes
    return _model, _vectorizer


def classify(text):
    """Predict a sentiment label ('negative' / 'neutral' / 'positive') for free text.

    This is the single place that turns text into a label: the form view and the
    `resentiment` command both call it. It uses the trained hybrid's own
    predict() (Naive Bayes when it is at least `threshold` confident, otherwise
    the Decision Tree), exactly as validated in the notebook. Do not replace it
    with a "highest percentage wins" comparison of the two sub-models: the tree's
    figure is a tiny leaf's class share (often exactly 100%), not a probability
    comparable to Naive Bayes', and that rule flipped clearly negative feedback
    to positive.
    """
    model, vectorizer = _load()
    features = vectorizer.transform([preprocess(text)])
    return str(model.predict(features)[0]).lower()


def _label_and_confidence(classifier, features):
    """(label, confidence) per row: the most probable class and its probability (0-1)."""
    proba = classifier.predict_proba(features)
    best = proba.argmax(axis=1)
    return [(str(classifier.classes_[i]).lower(), float(p[i])) for i, p in zip(best, proba)]


def component_predictions(texts):
    """Label each text with the hybrid's two sub-models separately.

    Returns {'threshold': float | None, 'rows': [...]}, where each row is
    {'nb': (label, confidence), 'dt': (label, confidence)} for one text, with
    lower-case labels and confidence as a 0-1 probability. For Naive Bayes
    that's its predicted class probability; for the Decision Tree it's the
    class share in the leaf the text lands in. `threshold` is the NB
    confidence the hybrid requires before trusting NB over the Decision Tree.
    `classify()` gives the hybrid's final answer.
    """
    if not texts:
        return {'threshold': None, 'rows': []}
    model, vectorizer = _load()
    features = vectorizer.transform([preprocess(t) for t in texts])
    nb = _label_and_confidence(model.nb_, features)
    dt = _label_and_confidence(model.dt_, features)
    return {
        'threshold': model.threshold,
        'rows': [{'nb': nb_row, 'dt': dt_row} for nb_row, dt_row in zip(nb, dt)],
    }
