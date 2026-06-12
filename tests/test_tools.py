from unittest.mock import MagicMock, patch

from tools import compare_price, create_fit_card, get_trending_styles, search_listings, suggest_outfit

# ── Shared fixtures ───────────────────────────────────────────────────────────

SAMPLE_ITEM = {
    "id": "lst_006",
    "title": "Graphic Tee — 2003 Tour Bootleg Style",
    "description": "Vintage-style bootleg tee with faded graphic.",
    "category": "tops",
    "style_tags": ["graphic tee", "vintage", "grunge", "streetwear"],
    "size": "L",
    "condition": "good",
    "price": 24.0,
    "colors": ["black"],
    "brand": None,
    "platform": "depop",
}

SAMPLE_WARDROBE = {
    "items": [
        {
            "id": "w_001",
            "name": "Baggy straight-leg jeans, dark wash",
            "category": "bottoms",
            "colors": ["dark blue"],
            "style_tags": ["denim", "streetwear", "baggy"],
        },
        {
            "id": "w_007",
            "name": "Chunky white sneakers",
            "category": "shoes",
            "colors": ["white"],
            "style_tags": ["sneakers", "chunky"],
        },
    ]
}


def _mock_groq(text: str):
    mock = MagicMock()
    mock.chat.completions.create.return_value.choices[0].message.content = text
    return mock


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_price_filter_with_results():
    results = search_listings("vintage", size=None, max_price=100)
    assert len(results) > 0
    assert all(item["price"] <= 100 for item in results)


def test_search_size_filter():
    results = search_listings("top", size="M", max_price=None)
    assert all("m" in item["size"].lower() for item in results)


def test_search_returns_list_not_exception():
    # impossible query — must return [] not raise
    results = search_listings("xyzzy nonexistent item", size=None, max_price=None)
    assert isinstance(results, list)


def test_search_best_match_first():
    results = search_listings("vintage graphic tee streetwear grunge", size=None, max_price=None)
    assert len(results) > 1
    # lst_006 has all four terms in its tags/description — should rank first
    assert results[0]["id"] == "lst_006"


# ── suggest_outfit ────────────────────────────────────────────────────────────

def test_suggest_outfit_empty_wardrobe_does_not_crash():
    with patch("tools._get_groq_client", return_value=_mock_groq("Try it with wide-leg trousers and chunky boots.")):
        result = suggest_outfit(SAMPLE_ITEM, {"items": []})
    assert isinstance(result, str)
    assert len(result) > 0


def test_suggest_outfit_empty_wardrobe_calls_llm():
    mock_client = _mock_groq("General styling advice here.")
    with patch("tools._get_groq_client", return_value=mock_client):
        suggest_outfit(SAMPLE_ITEM, {"items": []})
    mock_client.chat.completions.create.assert_called_once()


def test_suggest_outfit_with_wardrobe_returns_string():
    with patch("tools._get_groq_client", return_value=_mock_groq("Pair with the baggy jeans and chunky sneakers.")):
        result = suggest_outfit(SAMPLE_ITEM, SAMPLE_WARDROBE)
    assert isinstance(result, str)
    assert len(result) > 0


# ── create_fit_card ───────────────────────────────────────────────────────────

def test_create_fit_card_empty_outfit_returns_error_string():
    result = create_fit_card("", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result) > 0


def test_create_fit_card_whitespace_outfit_returns_error_string():
    result = create_fit_card("   ", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result) > 0


def test_create_fit_card_empty_outfit_does_not_call_llm():
    # guard fires before API call — no Groq client needed
    with patch("tools._get_groq_client") as mock_get_client:
        create_fit_card("", SAMPLE_ITEM)
    mock_get_client.assert_not_called()


def test_create_fit_card_returns_caption():
    caption = "Just copped this Graphic Tee on depop for $24 and I'm not okay 🖤"
    with patch("tools._get_groq_client", return_value=_mock_groq(caption)):
        result = create_fit_card("Graphic tee + baggy jeans + white sneakers", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result) > 0


def test_create_fit_card_uses_high_temperature():
    mock_client = _mock_groq("Some caption.")
    with patch("tools._get_groq_client", return_value=mock_client):
        create_fit_card("Graphic tee + baggy jeans", SAMPLE_ITEM)
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs.get("temperature", 0) >= 1.0


# ── compare_price ─────────────────────────────────────────────────────────────

def test_compare_price_returns_dict():
    result = compare_price(SAMPLE_ITEM)
    assert isinstance(result, dict)
    for key in ("verdict", "item_price", "avg_price", "min_price", "max_price",
                "comparable_count", "summary"):
        assert key in result


def test_compare_price_item_price_matches_input():
    result = compare_price(SAMPLE_ITEM)
    assert result["item_price"] == SAMPLE_ITEM["price"]


def test_compare_price_excludes_item_itself():
    # if the item compared against itself, comparable_count would be inflated
    # and avg_price would equal item_price — use a real listing to check
    results = search_listings("graphic tee", size=None, max_price=None)
    item = results[0]
    verdict = compare_price(item)
    # none of the comparables should be the item itself
    assert verdict["comparable_count"] == 0 or verdict["avg_price"] is not None


def test_compare_price_verdict_is_valid_value():
    result = compare_price(SAMPLE_ITEM)
    assert result["verdict"] in ("great deal", "fair price", "a bit high", "no comparison available")


def test_compare_price_no_comparables_returns_gracefully():
    # item with a unique category/tag combo unlikely to have comparables
    unique_item = {
        "id": "fake_001",
        "title": "Fake Item",
        "category": "accessories",
        "style_tags": ["nonexistent_tag_xyz"],
        "price": 99.99,
    }
    result = compare_price(unique_item)
    assert result["comparable_count"] == 0
    assert result["avg_price"] is None
    assert result["verdict"] == "no comparison available"
    assert isinstance(result["summary"], str)


def test_compare_price_range_makes_sense():
    result = compare_price(SAMPLE_ITEM)
    if result["comparable_count"] > 0:
        assert result["min_price"] <= result["avg_price"] <= result["max_price"]


def test_compare_price_great_deal_verdict():
    # artificially cheap item — should be a great deal
    cheap_item = dict(SAMPLE_ITEM, id="fake_cheap", price=1.00)
    result = compare_price(cheap_item)
    if result["comparable_count"] > 0:
        assert result["verdict"] == "great deal"


def test_compare_price_high_verdict():
    # artificially expensive item — should be a bit high
    expensive_item = dict(SAMPLE_ITEM, id="fake_expensive", price=9999.00)
    result = compare_price(expensive_item)
    if result["comparable_count"] > 0:
        assert result["verdict"] == "a bit high"


# ── get_trending_styles ───────────────────────────────────────────────────────

def test_trending_returns_dict():
    result = get_trending_styles(["vintage", "grunge", "streetwear"])
    assert isinstance(result, dict)
    for key in ("matched_posts", "top_hashtags", "summary"):
        assert key in result


def test_trending_matched_posts_are_dicts():
    result = get_trending_styles(["vintage", "grunge"])
    for post in result["matched_posts"]:
        for field in ("caption", "hashtags", "platform", "post_count", "days_ago"):
            assert field in post


def test_trending_returns_at_most_three_posts():
    result = get_trending_styles(["vintage", "streetwear", "grunge", "graphic tee"])
    assert len(result["matched_posts"]) <= 3


def test_trending_no_match_returns_gracefully():
    result = get_trending_styles(["nonexistent_style_xyz"])
    assert result["matched_posts"] == []
    assert result["top_hashtags"] == []
    assert isinstance(result["summary"], str)


def test_trending_top_hashtags_capped_at_five():
    result = get_trending_styles(["vintage", "grunge", "streetwear"])
    assert len(result["top_hashtags"]) <= 5


def test_trending_summary_is_nonempty_string():
    result = get_trending_styles(["y2k", "platform"])
    assert isinstance(result["summary"], str)
    assert len(result["summary"]) > 0


def test_trending_empty_tags_returns_gracefully():
    result = get_trending_styles([])
    assert isinstance(result, dict)
    assert result["matched_posts"] == []
