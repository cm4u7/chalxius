from __future__ import annotations

import math
import re
from collections import Counter


_TOKEN = re.compile(r"\\[A-Za-z]+|[A-Za-z][A-Za-z0-9_-]*|[0-9a-f]{8,16}|\d+")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN.findall(text)]


def bm25(query: str, documents: list[str], *, k1: float = 1.5, b: float = 0.75) -> list[float]:
    if not documents:
        return []
    tokenized = [tokenize(document) for document in documents]
    query_terms = set(tokenize(query))
    if not query_terms:
        return [0.0 for _ in documents]
    lengths = [len(tokens) for tokens in tokenized]
    average_length = sum(lengths) / max(1, len(lengths))
    frequencies = [Counter(tokens) for tokens in tokenized]
    document_frequency = {
        term: sum(1 for counts in frequencies if counts.get(term, 0) > 0)
        for term in query_terms
    }
    scores: list[float] = []
    total = len(documents)
    for counts, length in zip(frequencies, lengths):
        score = 0.0
        for term in query_terms:
            frequency = counts.get(term, 0)
            if not frequency:
                continue
            df = document_frequency[term]
            inverse_frequency = math.log(1.0 + (total - df + 0.5) / (df + 0.5))
            denominator = frequency + k1 * (
                1.0 - b + b * length / max(average_length, 1.0)
            )
            score += inverse_frequency * frequency * (k1 + 1.0) / denominator
        scores.append(score)
    return scores

