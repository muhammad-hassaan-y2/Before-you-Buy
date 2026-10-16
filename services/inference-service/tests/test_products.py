from byb_inference.products import category_for, extract_context, fallback_profile, parse_dimensions
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


def test_parse_dimensions_from_labeled_listing():
    dims = parse_dimensions("Width: 228 cm, Depth: 95 cm, Height: 80 cm")
    assert dims == {"width_cm": 228.0, "depth_cm": 95.0, "height_cm": 80.0}


def test_parse_dimensions_converts_metres_and_long_phrase():
    assert parse_dimensions("sofa 2.28 m long")["width_cm"] == 228.0
    assert parse_dimensions("height: 0.8 m")["height_cm"] == 80.0


def test_fallback_profile_prefers_listing_dimensions():
    profile = fallback_profile(extract_context(PAGE), "https://example.com/sofa")
    assert profile.source == "heuristic"
    assert profile.category == "sofa"
    assert profile.geometry.width_cm == 228.0
    assert profile.geometry.depth_cm == 95.0
    assert profile.geometry.height_cm == 80.0
    assert profile.confidence == 0.45
    assert profile.measurement_basis == "listing_verified"
    assert profile.dimension_reliability["width_cm"] == "verified"
    assert "listing evidence" in profile.summary.lower()


def test_fallback_profile_uses_category_when_no_sizes():
    profile = fallback_profile("og:title: Cosy grey sofa\nshopper notes: soft", None)
    assert profile.geometry.width_cm == 220.0
    assert profile.confidence == 0.25
    assert profile.measurement_basis == "category_estimate"
    assert all(v == "estimated" for v in profile.dimension_reliability.values())


def test_scan_json_finds_the_first_balanced_object():
    parsed = _scan_json('Sure! {"name": "Sofa", "dims": {"a": 1}} trailing } noise')
    assert parsed == {"name": "Sofa", "dims": {"a": 1}}
    assert _scan_json("no json here") is None
    assert _scan_json("{broken") is None


def test_to_profile_validates_and_clamps():
    profile = to_profile(
        {
            "name": "Bookshelf",
            "width_cm": 80,
            "depth_cm": "30",
            "height_cm": 180,
            "clearance_cm": 200,
        },
        model_id="example-model-id",
    )
    assert profile is not None
    assert profile.geometry.width_cm == 80
    assert profile.geometry.depth_cm == 30
    assert profile.geometry.height_cm == 180
    assert profile.geometry.clearance_cm == 150  # capped
    assert profile.source == "amd_token_factory"
    assert profile.provider == "amd_token_factory"
    assert profile.model == "example-model-id"
    assert profile.dimension_reliability["height_cm"] == "extracted"
    assert to_profile({"summary": "no name"}) is None
    assert to_profile({"name": "X", "width_cm": 5000, "depth_cm": 30, "height_cm": 180}) is None

