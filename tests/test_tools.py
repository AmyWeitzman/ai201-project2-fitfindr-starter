from unittest.mock import MagicMock, patch

from tools import create_fit_card, search_listings, suggest_outfit

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
