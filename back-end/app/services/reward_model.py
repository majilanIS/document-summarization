
"""Reward model learned from user feedback, the "RM" in RLHF.

A summary is described by a few features of how it relates to its source
(coverage, faithfulness, redundancy, ...). A linear model over them is fit
to the feedback the users gave:

- star ratings: pointwise, a higher rating means a higher reward;
- preferences: pairwise Bradley-Terry loss, as RLHF reward models use.
  Pairs come from explicit comparisons and from two summaries of the same
  document that got different ratings.

Weights are pulled toward a hand-set prior, so the model is sensible before
there is any feedback and moves away from it as feedback accumulates.

The summariser uses `score` to keep the best of several candidate summaries
(best-of-N sampling), so feedback changes what future summaries look like.
"""

import re
import threading
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache

import numpy as np

from app.db import get_connection
from app.services.prompt import extract_numbers


FEATURES = [
    "coverage",
    "support",
    "novelty",
    "redundancy",
    "compression",
    "sentence_length",
    "complete",
    "numbers_supported",
]

# Starting point before any feedback: cover the source's main terms, stick
# to its words and figures, don't repeat yourself, end on a full sentence.
PRIOR_WEIGHTS = np.array([1.0, 1.0, -0.3, -1.5, 0.0, 0.0, 0.5, 1.0])

# How strongly weights are held to the prior. Lower lets feedback move
# them further with less data.
PRIOR_STRENGTH = 0.05

# Feedback items needed before the learned weights replace the prior.
MIN_FEEDBACK = 3

TRAIN_STEPS = 500

STOPWORDS = frozenset(
    """a about above after again against all also am an and any are as at be
    because been before being below between both but by can could did do does
    doing down during each few for from further had has have having he her here
    hers him his how i if in into is it its itself just me more most my no nor
    not now of off on once only or other our ours out over own same she should
    so some such than that the their theirs them then there these they this
    those through to too under until up very was we were what when where which
    while who whom why will with would you your yours""".split()
)

WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _words(text: str) -> list[str]:
    return WORD.findall(text.lower())


def _content_words(words: list[str]) -> list[str]:
    return [w for w in words if w not in STOPWORDS and len(w) > 2]


def _trigrams(words: list[str]) -> list[tuple]:
    return list(zip(words, words[1:], words[2:]))


@lru_cache(maxsize=64)
def _source_profile(source: str):
    """Things about the source every candidate is compared with. Cached
    because every candidate of a chunk shares the same source."""
    words = _words(source)
    content = _content_words(words)
    top_terms = {w for w, _ in Counter(content).most_common(20)}
    return (
        len(words) or 1,
        set(content),
        top_terms,
        set(_trigrams(words)),
        extract_numbers(source),
    )


def features(source: str, summary: str) -> np.ndarray:
    """Feature vector (in FEATURES order), each roughly in [0, 1]."""
    (
        source_words,
        source_vocab,
        top_terms,
        source_trigrams,
        source_numbers,
    ) = _source_profile(source)

    words = _words(summary)
    if not words:
        return np.zeros(len(FEATURES))

    content = _content_words(words)
    trigrams = _trigrams(words)
    sentences = [s for s in SENTENCE_END.split(summary.strip()) if s]

    # Share of the source's main terms that made it into the summary.
    coverage = len(top_terms & set(content)) / len(top_terms) if top_terms else 0.0
    # Share of the summary's terms that appear in the source (made-up
    # terms suggest hallucination).
    support = (
        sum(w in source_vocab for w in content) / len(content) if content else 1.0
    )
    # Phrasing not copied from the source.
    novelty = (
        sum(t not in source_trigrams for t in trigrams) / len(trigrams)
        if trigrams else 0.0
    )
    # Phrases the summary repeats.
    redundancy = 1 - len(set(trigrams)) / len(trigrams) if trigrams else 0.0
    compression = min(1.0, len(words) / source_words)
    sentence_length = min(2.0, len(words) / max(1, len(sentences)) / 25)
    complete = 1.0 if summary.rstrip()[-1:] in ".!?\"')" else 0.0
    # Share of the summary's figures found in the source; invented
    # numbers are the most common and most harmful hallucination.
    numbers = extract_numbers(summary)
    numbers_supported = (
        len(numbers & source_numbers) / len(numbers) if numbers else 1.0
    )

    return np.array([
        coverage,
        support,
        novelty,
        redundancy,
        compression,
        sentence_length,
        complete,
        numbers_supported,
    ])


class RewardModel:
    def __init__(self):
        self.weights = PRIOR_WEIGHTS.copy()
        self.bias = 0.0
        self.ratings = 0
        self.pairs = 0
        self.trained_at = None
        self._lock = threading.Lock()

    @property
    def learned(self) -> bool:
        return self.ratings + self.pairs >= MIN_FEEDBACK

    def score(self, source: str, summary: str) -> float:
        return float(features(source, summary) @ self.weights + self.bias)

    def best(self, source: str, candidates: list[str]) -> tuple[str, float]:
        """The candidate with the highest reward, and that reward."""
        scored = [(self.score(source, c), c) for c in candidates if c.strip()]
        if not scored:
            return "", 0.0
        reward, best = max(scored, key=lambda pair: pair[0])
        return best, reward

    def train(self) -> None:
        """Refit to all feedback in the database. Fast: a few hundred
        feedback items train in well under a second."""
        rated, pairs = _load_training_data()

        weights = PRIOR_WEIGHTS.copy()
        bias = 0.0

        if len(rated) + len(pairs) >= MIN_FEEDBACK:
            weights, bias = _fit(rated, pairs)

        with self._lock:
            self.weights, self.bias = weights, bias
            self.ratings, self.pairs = len(rated), len(pairs)
            self.trained_at = datetime.now(timezone.utc).isoformat()

    def status(self) -> dict:
        return {
            "mode": "learned" if self.learned else "prior",
            "ratings": self.ratings,
            "pairs": self.pairs,
            "min_feedback": MIN_FEEDBACK,
            "trained_at": self.trained_at,
            "weights": [
                {
                    "feature": name,
                    "weight": round(float(w), 3),
                    "prior": float(p),
                }
                for name, w, p in zip(FEATURES, self.weights, PRIOR_WEIGHTS)
            ],
        }


def _fit(rated, pairs) -> tuple[np.ndarray, float]:
    """Gradient descent on squared error for ratings plus Bradley-Terry
    log-loss for preferences, with an L2 pull toward the prior."""
    w = PRIOR_WEIGHTS.copy()
    b = 0.0

    if rated:
        x_rated = np.array([x for x, _ in rated])
        # 1..5 stars -> -1..1
        y_rated = np.array([(r - 3) / 2 for _, r in rated])
    if pairs:
        x_diff = np.array([win - lose for win, lose in pairs])

    # Step size 1/L, where L bounds the loss's curvature, so gradient
    # descent can't diverge whatever the features look like. (The bias
    # column is the +1; the pairwise log-loss curvature is at most 1/4.)
    curvature = PRIOR_STRENGTH
    if rated:
        with_bias = np.hstack([x_rated, np.ones((len(rated), 1))])
        curvature += np.linalg.norm(with_bias, 2) ** 2 / len(rated)
    if pairs:
        curvature += np.linalg.norm(x_diff, 2) ** 2 / (4 * len(pairs))
    step = 1 / curvature

    for _ in range(TRAIN_STEPS):
        grad_w = PRIOR_STRENGTH * (w - PRIOR_WEIGHTS)
        grad_b = 0.0

        if rated:
            error = x_rated @ w + b - y_rated
            grad_w += x_rated.T @ error / len(rated)
            grad_b += error.mean()

        if pairs:
            # d/dw of -log(sigmoid(w . (x_win - x_lose)))
            p_wrong = 1 / (1 + np.exp(x_diff @ w))
            grad_w -= x_diff.T @ p_wrong / len(pairs)

        w -= step * grad_w
        b -= step * grad_b

    return w, b


def _load_training_data():
    """([(features, rating)], [(winner features, loser features)])"""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT f.summary_id, f.rating, f.summary_a_id, f.summary_b_id,
                   f.preferred, f.document_id
            FROM feedback f
            """
        ).fetchall()

        summary_ids = {
            sid
            for r in rows
            for sid in (r["summary_id"], r["summary_a_id"], r["summary_b_id"])
            if sid
        }
        summaries = {
            s["id"]: s
            for s in conn.execute(
                f"""
                SELECT id, text, document_id FROM summaries
                WHERE id IN ({",".join("?" * len(summary_ids))})
                """,
                list(summary_ids),
            )
        } if summary_ids else {}

        # Each document's text once, however many of its summaries were rated.
        document_ids = {s["document_id"] for s in summaries.values()}
        sources = {
            d["id"]: d["clean_text"]
            for d in conn.execute(
                f"""
                SELECT id, clean_text FROM documents
                WHERE id IN ({",".join("?" * len(document_ids))})
                """,
                list(document_ids),
            )
        } if document_ids else {}

    cache = {}

    def feats(summary_id):
        if summary_id not in cache:
            s = summaries[summary_id]
            cache[summary_id] = features(sources[s["document_id"]], s["text"])
        return cache[summary_id]

    rated = []
    pairs = []
    # Average rating per summary, grouped by document, for implied pairs.
    by_document = {}

    for r in rows:
        if r["rating"] is not None and r["summary_id"] in summaries:
            rated.append((feats(r["summary_id"]), r["rating"]))
            by_document.setdefault(r["document_id"], {}).setdefault(
                r["summary_id"], []
            ).append(r["rating"])

        elif (
            r["preferred"] in ("a", "b")
            and r["summary_a_id"] in summaries
            and r["summary_b_id"] in summaries
        ):
            a, b = feats(r["summary_a_id"]), feats(r["summary_b_id"])
            pairs.append((a, b) if r["preferred"] == "a" else (b, a))

    for ratings in by_document.values():
        averages = [(sum(v) / len(v), sid) for sid, v in ratings.items()]
        for i, (rating_i, id_i) in enumerate(averages):
            for rating_j, id_j in averages[i + 1:]:
                if rating_i > rating_j:
                    pairs.append((feats(id_i), feats(id_j)))
                elif rating_j > rating_i:
                    pairs.append((feats(id_j), feats(id_i)))

    return rated, pairs


reward_model = RewardModel()
