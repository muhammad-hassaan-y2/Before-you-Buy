"""Read a product page and produce a usable prompt context, plus the heuristics used
when no vLLM endpoint answers."""

from __future__ import annotations

import html
import re

import httpx

from byb_common.contracts import ProductGeometry, ProductProfile

_TAG = re.compile(r"<[^>]+>")
_META = re.compile(
    r"""<meta[^>]+(?:property|name)=["'](?P<key>og:title|og:description|description|twitter:title)["'][^>]*>""",
    re.IGNORECASE,
)
_CONTENT = re.compile(r"""content=["'](?P<value>.*?)["']""", re.IGNORECASE)
_TITLE = re.compile(r"<title[^>]*>(?P<value>.*?)</title>", re.IGNORECASE | re.DOTALL)
_LD_PRODUCT = re.compile(r'"@type"\s*:\s*"Product"', re.IGNORECASE)
_JSON_FIELDS = re.compile(r'"(?P<key>name|description|width|depth|height|mat(?:erial)?)"\s*:\s*"(?P<value>[^"]{1,200})"')

# Typical real-world footprints, in cm: (width, depth, height, clearance).
HEURISTICS: dict[str, tuple[int, int, int, int]] = {
    "sofa": (220, 95, 85, 90),
    "sectional": (260, 160, 80, 90),
    "armchair": (90, 90, 100, 60),
    "dining table": (180, 90, 75, 80),
    "desk": (140, 70, 75, 70),
    "bookshelf": (80, 30, 180, 60),
    "wardrobe": (120, 60, 200, 70),
    "bed": (160, 200, 105, 70),
    "chair": (50, 55, 85, 60),
    "coffee table": (110, 60, 45, 60),
    "rug": (160, 230, 2, 0),
    "floor lamp": (40, 40, 165, 50),
    "tv stand": (150, 40, 50, 60),
}


def _clean(value: str) -> str:
    return html.unescape(value).strip()


def extract_context(body: str) -> str:
    """Squeeze the useful strings out of a product page without an HTML parser."""
    parts: list[str] = []
    for match in _META.finditer(body):
        content = _CONTENT.search(match.group(0))
        if content:
            parts.append(f"{match.group('key')}: {_clean(content.group('value'))}")
    if (title := _TITLE.search(body)):
        parts.append(f"title: {_clean(title.group('value'))}")
    if _LD_PRODUCT.search(body):
        for field in _JSON_FIELDS.finditer(body):
            parts.append(f"{field.group('key')}: {_clean(field.group('value'))}")
    text = "\n".join(dict.fromkeys(parts))
    return _TAG.sub(" ", text)[:2500]


def category_for(text: str) -> str:
    lowered = text.lower()
    for keyword in HEURISTICS:
        if keyword in lowered:
            return keyword
    return "furniture"


def fallback_profile(context: str, link: str | None) -> ProductProfile:
    width, depth, height, clearance = HEURISTICS.get(category_for(context), (100, 60, 80, 60))
    title = next(
        (line.split(":", 1)[1].strip() for line in context.splitlines() if line.startswith(("og:title", "title"))),
        None,
    )
    name = title or (f"{category_for(context).title()} from {link}" if link else "Unidentified product")
    return ProductProfile(
        name=name[:120],
        category=category_for(context),
        geometry=ProductGeometry(
            width_cm=float(width), depth_cm=float(depth), height_cm=float(height), clearance_cm=float(clearance)
        ),
        confidence=0.25,
        summary="Dimensions come from the built-in category heuristics because no vLLM endpoint answered.",
        source="heuristic",
    )
