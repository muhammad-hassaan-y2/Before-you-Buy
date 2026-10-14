from byb_inference.products import category_for, extract_context, fallback_profile
from byb_inference.vllm_client import _scan_json, to_profile

PAGE = """
<html><head>
<title>IKEA.com - LINNROER 3-seat sofa</title>
<meta property="og:title" content="LINNROER 3-seat sofa, Skettebose grey">
<meta property="og:description" content="3-seat sofa, 228 cm long, polyester blends">
<meta name="description" content="Width: 228 cm, Depth: 95 cm, Height: 80 cm">
<script>{"@context":"https://schema.org","@type":"Product","name":"LINNROER","width":"228 cm","material":"polyester"}</script>
</head><body></body></html>
"""


def test_extract_context_pulls_meta_and_jsonld():
    context = extract_context(PAGE)
    assert "LINNROER 3-seat sofa, Skettebose grey" in context
    assert "width" in context.lower()
    assert "<" not in context


def test_category_matches_known_furniture():
    assert category_for("a corner sectional with chaise") == "sectional"
    assert category_for("walnut writing Desk") == "desk"
    assert category_for("ceramic mug") == "furniture"


def test_fallback_profile_uses_category_heuristics():
    profile = fallback_profile(extract_context(PAGE), "https://example.com/sofa")
    assert profile.source == "heuristic"
    assert profile.category == "sofa"
    assert profile.geometry.width_cm == 220
    assert profile.confidence < 0.5


def test_scan_json_finds_the_first_balanced_object():
    parsed = _scan_json('Sure! {"name": "Sofa", "dims": {"a": 1}} trailing } noise')
    assert parsed == {"name": "Sofa", "dims": {"a": 1}}
    assert _scan_json("no json here") is None
    assert _scan_json("{broken") is None


def test_to_profile_clamps_and_defaults():
    profile = to_profile({"name": "Bookshelf", "width_cm": 5000, "depth_cm": "30", "height_cm": None})
    assert profile is not None
    assert profile.geometry.width_cm == 800  # clamped to the sane ceiling
    assert profile.geometry.depth_cm == 30
    assert profile.geometry.height_cm == 80  # defaulted
    assert profile.source == "vllm"
    assert to_profile({"summary": "no name"}) is None
