"""Fuzzy matching of a product link or free-text notes against the seeded catalog.

Scoring is deliberately dumb and explainable: a phrase hit from `aliases` is worth far more
than a shared word, brand and category nudge the result, and everything below `min_score`
is reported as no-match so inference-service keeps its vLLM path.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from byb_catalog.settings import settings
from byb_catalog.skus import CATALOG, Sku
from byb_common.contracts import CatalogCandidate

STOP_WORDS = {
    "the", "a", "an", "and", "of", "with", "for", "to", "in", "on", "buy", "shop", "product", "p", "sku",
    "www", "com", "co", "uk", "us", "html", "htm", "page", "item", "new", "sale",
}
WORD = re.compile(r"[a-z0-9]+")
NOISE = re.compile(r"[^a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return [word for word in WORD.findall((text or "").lower()) if word not in STOP_WORDS and len(word) > 1]


def slug_text(link: str) -> str:
    """Turn `https://x.com/p/billy-bookcase-803-999/` into `billy bookcase`."""
    if not link:
        return ""
    pieces = urlsplit(link)
    words = NOISE.sub(" ", f"{pieces.path} {pieces.query} {pieces.fragment}").split()
    # A bare number carries no meaning, but "2x2" or "180x80" does.
    return " ".join(word for word in words if not word.isdigit())


def _overlap(haystack: set[str], words: list[str]) -> int:
    return len(haystack.intersection(words))


def score_item(item: Sku, words: list[str], raw: str) -> float:
    if not words:
        return 0.0
    vocabulary = item.tokens()
    phrase = 0.0
    for alias in (*item.aliases, f"{item.brand} {item.category}", item.name):
        normalised = NOISE.sub(" ", alias.lower()).strip()
        if normalised and normalised in raw and len(normalised.split()) > 1:
            phrase = max(phrase, 0.55)

    token_hit = _overlap(vocabulary, words) / max(len(words), 1)
    brand_hit = 0.2 if item.brand.lower() in words else 0.0
    category_hit = 0.18 if item.category in words else 0.0
    name_hit = _overlap({word for word in item.name.lower().split()}, words) * 0.12

    return min(1.0, phrase + token_hit * 0.45 + brand_hit + category_hit + name_hit)


def best_match(text: str) -> tuple[Sku, float] | None:
    raw = NOISE.sub(" ", (text or "").lower())
    raw = f" {raw} "
    words = tokenize(text)
    ranked = sorted(((item, score_item(item, words, raw)) for item in CATALOG), key=lambda pair: pair[1], reverse=True)
    top, score = ranked[0]
    if score < settings.min_match_score:
        return None
    return top, score


def candidate_for(*sources: str | None) -> CatalogCandidate | None:
    """Best SKU across several text sources, e.g. the product link and the shopper's notes."""
    words = [slug_text(source) if "://" in source else source for source in sources if source]
    if not words:
        return None
    matched = best_match(" ".join(words))
    if matched is None:
        return None
    item, score = matched
    return item.as_candidate(score)
