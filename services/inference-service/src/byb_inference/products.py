"""Product page extraction and heuristic ProductProfile fallback.

Extends listing context (meta, JSON-LD, tables, descriptions) and dimension parsing
(mm/cm/m/inches) while preferring assembled product sizes over package/shipping.
"""

from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser

from byb_common.contracts import CatalogCandidate, ProductGeometry, ProductProfile
from byb_common.parts import build_parts

_TAG = re.compile(r"<[^>]+>")
_META = re.compile(
    r"""<meta[^>]+(?:property|name)=["'](?P<key>og:title|og:description|description|twitter:title|twitter:description)["'][^>]*>""",
    re.IGNORECASE,
)
_CONTENT = re.compile(r"""content=["'](?P<value>.*?)["']""", re.IGNORECASE)
_TITLE = re.compile(r"<title[^>]*>(?P<value>.*?)</title>", re.IGNORECASE | re.DOTALL)
_SCRIPT_LD = re.compile(
    r"""<script[^>]*type=["']application/ld\+json["'][^>]*>(?P<body>.*?)</script>""",
    re.IGNORECASE | re.DOTALL,
)

_LABELED_DIM = re.compile(
    r"(?P<label>width|depth|height|length|w|d|h)\s*[:=]?\s*(?P<value>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>cm|mm|m|in(?:ch(?:es)?)?|\"|'')\b",
    re.IGNORECASE,
)
_LONG_PHRASE = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>cm|mm|m|in(?:ch(?:es)?)?)\s+(?:long|wide|width)\b",
    re.IGNORECASE,
)

_PACKAGE_HINT = re.compile(
    r"\b(package|packaging|shipping|carton|boxed|box\s*size|parcel|delivery\s*dimensions?)\b",
    re.IGNORECASE,
)
_SEAT_HINT = re.compile(r"\b(seat\s*(height|depth|width)|sitting\s*height)\b", re.IGNORECASE)
_ASSEMBLED_HINT = re.compile(
    r"\b(product\s*dimensions?|assembled|overall|item\s*dimensions?|finished\s*size)\b",
    re.IGNORECASE,
)

MAX_DIMENSION_CM = 800.0
MAX_CONTEXT_CHARS = 4000

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


def _to_cm(value: str, unit: str) -> float | None:
    try:
        number = float(value.replace(",", "."))
    except ValueError:
        return None
    normalized = unit.lower().strip().strip("'").strip('"')
    if normalized in {"mm"}:
        number /= 10.0
    elif normalized in {"m"}:
        number *= 100.0
    elif normalized in {"in", "inch", "inches", '"', "''"}:
        number *= 2.54
    elif normalized not in {"cm"}:
        return None
    if number < 1.0 or number > MAX_DIMENSION_CM:
        return None
    return round(number, 2)


def _dim_kind_at(text: str, index: int) -> str:
    """Classify using preceding context so later 'package' lines do not pollute product dims."""
    left = text[max(0, index - 70) : index]
    if _PACKAGE_HINT.search(left):
        return "package"
    if _SEAT_HINT.search(left):
        return "seat"
    return "assembled"


def _label_to_key(label: str) -> str | None:
    return {
        "width": "width_cm",
        "w": "width_cm",
        "length": "width_cm",
        "depth": "depth_cm",
        "d": "depth_cm",
        "height": "height_cm",
        "h": "height_cm",
    }.get(label.lower())


def parse_dimensions(text: str, *, kind: str = "assembled") -> dict[str, float]:
    """Pull width/depth/height in cm. `kind` filters assembled|package|seat."""
    found: dict[str, float] = {}
    for match in _LABELED_DIM.finditer(text):
        key = _label_to_key(match.group("label"))
        if not key or key in found:
            continue
        if _dim_kind_at(text, match.start()) != kind:
            continue
        cm = _to_cm(match.group("value"), match.group("unit"))
        if cm is not None:
            found[key] = cm
    if kind == "assembled" and "width_cm" not in found:
        if (long_match := _LONG_PHRASE.search(text)):
            if _dim_kind_at(text, long_match.start()) == "assembled":
                cm = _to_cm(long_match.group("value"), long_match.group("unit"))
                if cm is not None:
                    found["width_cm"] = cm
    return found


def _walk_json_ld(node: object, lines: list[str]) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_json_ld(item, lines)
        return
    if not isinstance(node, dict):
        return
    types = node.get("@type")
    type_names = types if isinstance(types, list) else [types]
    type_names = [str(t).lower() for t in type_names if t]
    if any("product" in t for t in type_names):
        for key in ("name", "description", "material", "brand", "sku", "category"):
            value = node.get(key)
            if isinstance(value, dict) and "name" in value:
                value = value.get("name")
            if isinstance(value, str) and value.strip():
                lines.append(f"jsonld.{key}: {_clean(value)[:400]}")
        for key in ("width", "depth", "height"):
            value = node.get(key)
            if value is not None:
                lines.append(f"jsonld.{key}: {_clean(str(value))}")
        for measure_key in ("additionalProperty", "size"):
            props = node.get(measure_key)
            if isinstance(props, list):
                for prop in props:
                    if isinstance(prop, dict):
                        name = prop.get("name") or prop.get("propertyID")
                        val = prop.get("value")
                        if name and val is not None:
                            lines.append(f"jsonld.spec {_clean(str(name))}: {_clean(str(val))}")
            elif isinstance(props, str):
                lines.append(f"jsonld.size: {_clean(props)}")
    for value in node.values():
        if isinstance(value, (dict, list)):
            _walk_json_ld(value, lines)


def _extract_json_ld_lines(body: str) -> list[str]:
    lines: list[str] = []
    for match in _SCRIPT_LD.finditer(body):
        raw = match.group("body").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Keep a truncated raw snippet for the LLM when JSON is slightly broken.
            lines.append(f"jsonld.raw: {_TAG.sub(' ', raw)[:500]}")
            continue
        _walk_json_ld(data, lines)
    return lines


class _TableCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_tr = False
        self._in_cell = False
        self._cell_tag = ""
        self._cell_parts: list[str] = []
        self._row: list[str] = []
        self.rows: list[tuple[str, str]] = []
        self._capture_p = False
        self._p_parts: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        if lower == "tr":
            self._in_tr = True
            self._row = []
        elif lower in {"th", "td"} and self._in_tr:
            self._in_cell = True
            self._cell_tag = lower
            self._cell_parts = []
        elif lower == "p":
            attr_map = {k.lower(): (v or "") for k, v in attrs}
            blob = " ".join(attr_map.values()).lower()
            if any(token in blob for token in ("description", "product", "detail", "spec")):
                self._capture_p = True
                self._p_parts = []

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower in {"th", "td"} and self._in_cell:
            text = _clean(" ".join(self._cell_parts))
            self._row.append(text)
            self._in_cell = False
        elif lower == "tr" and self._in_tr:
            self._in_tr = False
            cells = [c for c in self._row if c]
            if len(cells) >= 2:
                self.rows.append((cells[0], cells[1]))
            elif len(cells) == 1 and ":" in cells[0]:
                left, right = cells[0].split(":", 1)
                self.rows.append((_clean(left), _clean(right)))
        elif lower == "p" and self._capture_p:
            text = _clean(" ".join(self._p_parts))
            if text:
                self.paragraphs.append(text[:500])
            self._capture_p = False

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_parts.append(data)
        if self._capture_p:
            self._p_parts.append(data)


def _extract_tables_and_descriptions(body: str) -> list[str]:
    parser = _TableCollector()
    try:
        parser.feed(body)
        parser.close()
    except Exception:
        return []
    lines: list[str] = []
    for label, value in parser.rows[:40]:
        lines.append(f"spec {label}: {value}")
    for paragraph in parser.paragraphs[:5]:
        lines.append(f"description: {paragraph}")
    return lines


def extract_context(body: str) -> str:
    """Build model/heuristic evidence from a product HTML page."""
    parts: list[str] = []
    for match in _META.finditer(body):
        content = _CONTENT.search(match.group(0))
        if content:
            parts.append(f"{match.group('key')}: {_clean(content.group('value'))}")
    if (title := _TITLE.search(body)):
        parts.append(f"title: {_clean(title.group('value'))}")
    parts.extend(_extract_json_ld_lines(body))
    parts.extend(_extract_tables_and_descriptions(body))

    assembled = parse_dimensions("\n".join(parts) + "\n" + _TAG.sub(" ", body)[:3000], kind="assembled")
    package = parse_dimensions("\n".join(parts) + "\n" + _TAG.sub(" ", body)[:3000], kind="package")
    if assembled:
        parts.append(
            "assembled_dimensions_cm: "
            + ", ".join(f"{k.replace('_cm', '')}={v:g}" for k, v in sorted(assembled.items()))
        )
    if package:
        parts.append(
            "package_dimensions_cm: "
            + ", ".join(f"{k.replace('_cm', '')}={v:g}" for k, v in sorted(package.items()))
            + " (shipping/package — do not use as product footprint)"
        )

    text = "\n".join(dict.fromkeys(parts))
    return _TAG.sub(" ", text)[:MAX_CONTEXT_CHARS]


def build_enrichment_context(page_html: str, shopper_notes: str | None = None) -> str:
    """Context string passed to Token Factory and heuristics."""
    context = extract_context(page_html) if page_html else ""
    if shopper_notes:
        context = f"{context}\nshopper notes: {shopper_notes.strip()}".strip()
    return context


def category_for(text: str) -> str:
    lowered = text.lower()
    for keyword in HEURISTICS:
        if keyword in lowered:
            return keyword
    return "furniture"


def fallback_profile(context: str, link: str | None) -> ProductProfile:
    category = category_for(context)
    width, depth, height, clearance = HEURISTICS.get(category, (100, 60, 80, 60))
    scraped = parse_dimensions(context, kind="assembled")

    reliability: dict[str, str] = {}
    values = {
        "width_cm": float(width),
        "depth_cm": float(depth),
        "height_cm": float(height),
    }
    for key in ("width_cm", "depth_cm", "height_cm"):
        if key in scraped:
            # Listing labels / JSON-LD / tables — extracted evidence, not a model claim.
            values[key] = float(scraped[key])
            reliability[key] = "verified"
        else:
            reliability[key] = "estimated"

    title = next(
        (
            line.split(":", 1)[1].strip()
            for line in context.splitlines()
            if line.startswith(("og:title", "title", "jsonld.name"))
        ),
        None,
    )
    name = title or (f"{category.title()} from {link}" if link else "Unidentified product")

    verified = [key for key, status in reliability.items() if status == "verified"]
    estimated = [key for key, status in reliability.items() if status == "estimated"]

    if verified and not estimated:
        measurement_basis = "listing_verified"
        summary = (
            "Heuristic path; all footprint axes taken from listing evidence "
            f"({', '.join(f'{k}={values[k]:g}cm' for k in verified)}). Not AMD Token Factory."
        )
        confidence = 0.45
    elif verified:
        measurement_basis = "listing_partial"
        summary = (
            f"Heuristic path; verified {verified} from listing; "
            f"estimated {estimated} via category '{category}' (not verified)."
        )
        confidence = 0.35
    else:
        measurement_basis = "category_estimate"
        summary = (
            "Heuristic path; no parseable assembled sizes — "
            f"category '{category}' estimates only (not verified)."
        )
        confidence = 0.25

    return ProductProfile(
        name=name[:120],
        category=category,
        geometry=ProductGeometry(
            width_cm=values["width_cm"],
            depth_cm=values["depth_cm"],
            height_cm=values["height_cm"],
            clearance_cm=float(clearance),
        ),
        parts=build_parts(category, values["width_cm"], values["depth_cm"], values["height_cm"]),
        confidence=confidence,
        summary=summary,
        source="heuristic",
        provider=None,
        model=None,
        dimension_reliability=reliability,
        measurement_basis=measurement_basis,
    )


def profile_from_candidate(candidate: CatalogCandidate) -> ProductProfile:
    """A catalog hit is a published box size, so it outranks a guess."""
    return ProductProfile(
        name=candidate.name,
        brand=candidate.brand,
        category=candidate.category,
        material=candidate.material,
        price_band=candidate.price_band,
        geometry=candidate.geometry,
        parts=candidate.parts,
        confidence=max(0.6, candidate.score),
        summary=f"Matched catalog SKU {candidate.sku} from the listing text; the room is sized around those published dimensions.",
        source="catalog",
    )


def best_profile(*profiles: ProductProfile | None) -> ProductProfile | None:
    """Highest confidence wins, ties going to the earlier argument."""
    ranked = [profile for profile in profiles if profile is not None]
    if not ranked:
        return None
    return max(enumerate(ranked), key=lambda pair: (pair[1].confidence, -pair[0]))[1]
