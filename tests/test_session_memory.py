"""
Tests for session-level style tag accumulation.
Uses mocks so no Groq API key is needed.
"""

from unittest.mock import MagicMock, patch

from app import handle_query


def _mock_session(item_style_tags):
    """Return a fake successful session with the given style tags on the item."""
    return {
        "error": None,
        "selected_item": {
            "title": "Test Item",
            "category": "tops",
            "size": "M",
            "condition": "good",
            "price": 25.0,
            "platform": "depop",
            "colors": ["black"],
            "brand": None,
            "description": "A test item.",
            "style_tags": item_style_tags,
        },
        "outfit_suggestion": "Pair with jeans.",
        "fit_card": "Found this gem on depop for $25!",
        "price_verdict": {
            "comparable_count": 3,
            "item_price": 25.0,
            "avg_price": 28.0,
            "min_price": 20.0,
            "max_price": 35.0,
            "verdict": "fair price",
            "summary": "Fair price.",
        },
    }


def test_style_tags_start_empty_and_grow():
    with patch("app.run_agent", return_value=_mock_session(["vintage", "streetwear"])):
        _, _, _, _, tags = handle_query("graphic tee", "Example wardrobe", [])

    assert "vintage" in tags
    assert "streetwear" in tags


def test_style_tags_accumulate_across_searches():
    with patch("app.run_agent", return_value=_mock_session(["vintage", "grunge"])):
        _, _, _, _, tags_1 = handle_query("graphic tee", "Example wardrobe", [])

    with patch("app.run_agent", return_value=_mock_session(["y2k", "streetwear"])):
        _, _, _, _, tags_2 = handle_query("baby tee", "Example wardrobe", tags_1)

    assert set(tags_2) == {"vintage", "grunge", "y2k", "streetwear"}


def test_style_tags_passed_to_run_agent():
    """Verify run_agent receives the accumulated tags as style_tags."""
    existing_tags = ["vintage", "grunge"]
    with patch("app.run_agent", return_value=_mock_session([])) as mock_run:
        handle_query("jacket", "Example wardrobe", existing_tags)

    call_kwargs = mock_run.call_args.kwargs
    assert call_kwargs.get("style_tags") == existing_tags


def test_empty_query_does_not_update_tags():
    existing_tags = ["vintage"]
    _, _, _, _, returned_tags = handle_query("", "Example wardrobe", existing_tags)
    assert returned_tags == existing_tags


def test_error_result_does_not_update_tags():
    error_session = {"error": "No listings found.", "selected_item": None,
                     "outfit_suggestion": None, "fit_card": None, "price_verdict": None}
    existing_tags = ["vintage"]
    with patch("app.run_agent", return_value=error_session):
        _, _, _, _, returned_tags = handle_query("ballgown", "Example wardrobe", existing_tags)

    assert returned_tags == existing_tags
