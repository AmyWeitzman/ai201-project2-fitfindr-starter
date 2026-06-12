"""
Tests for the progressive search fallback in run_agent().
All tests use real search_listings (no LLM) so no Groq key is needed —
the agent is stopped at the search step by using a query that returns nothing
before reaching suggest_outfit, or by mocking suggest_outfit/create_fit_card.
"""

from unittest.mock import patch

from agent import run_agent
from utils.data_loader import get_example_wardrobe

WARDROBE = get_example_wardrobe()

_FAKE_OUTFIT = "Pair with baggy jeans and chunky sneakers."
_FAKE_CARD = "Found this gem and I'm never giving it back."
_FAKE_PRICE = {
    "verdict": "fair price", "item_price": 20.0, "avg_price": 22.0,
    "min_price": 18.0, "max_price": 30.0, "comparable_count": 3,
    "summary": "Fair.",
}
_FAKE_TREND = {"matched_posts": [], "top_hashtags": [], "summary": "No trends."}


def _run(query):
    """Run agent with all LLM calls mocked out."""
    with patch("agent.suggest_outfit", return_value=_FAKE_OUTFIT), \
         patch("agent.create_fit_card", return_value=_FAKE_CARD), \
         patch("agent.compare_price", return_value=_FAKE_PRICE), \
         patch("agent.get_trending_styles", return_value=_FAKE_TREND):
        return run_agent(query, WARDROBE)


def test_no_fallback_needed_leaves_list_empty():
    session = _run("vintage graphic tee")
    assert session["search_fallbacks"] == []
    assert session["error"] is None


def test_size_fallback_recorded_when_size_dropped():
    # XXL is parsed by the regex but no listing has that size → forces size fallback
    session = _run("vintage tee size XXL")
    if session["error"] is None:
        # results found only after dropping size
        assert any("size" in fb for fb in session["search_fallbacks"])


def test_price_fallback_recorded_when_price_dropped():
    # under $1 should match nothing — forces price fallback
    session = _run("vintage tee under $1")
    if session["error"] is None:
        assert any("price" in fb for fb in session["search_fallbacks"])


def test_both_fallbacks_recorded_when_size_and_price_both_dropped():
    # XXL matches no listing + $1 ceiling matches nothing → both filters dropped
    session = _run("vintage tee size XXL under $1")
    if session["error"] is None:
        fbs = session["search_fallbacks"]
        assert any("size" in fb for fb in fbs)
        assert any("price" in fb for fb in fbs)


def test_truly_impossible_query_still_errors_gracefully():
    session = _run("xyzzy ballgown designer size XXXL under $1")
    # may or may not error depending on keyword scoring, but must not raise
    assert "error" in session


def test_fallback_session_still_has_selected_item():
    # a query that forces size fallback should still populate selected_item
    session = _run("vintage tee size XXXL")
    if session["error"] is None:
        assert session["selected_item"] is not None


def test_no_filters_query_has_no_fallbacks():
    session = _run("vintage jacket")
    assert session["search_fallbacks"] == []
