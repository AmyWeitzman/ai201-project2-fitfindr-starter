"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card, compare_price, get_trending_styles


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "price_verdict": None,       # dict returned by compare_price
        "trend_report": None,        # dict returned by get_trending_styles
        "error": None,               # set if the interaction ended early
    }


# ── query parser ─────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query
    using regex. Falls back to the full query text as the description if
    nothing useful can be stripped out.
    """
    text = query.lower()

    # max_price: "under $30", "up to $40", "below $25", "$30 or less"
    price_match = re.search(
        r'(?:under|max|up to|below|for)\s*\$(\d+(?:\.\d+)?)'
        r'|\$(\d+(?:\.\d+)?)\s*(?:or less|max)',
        text,
    )
    max_price = None
    if price_match:
        raw = price_match.group(1) or price_match.group(2)
        max_price = float(raw)

    # size: "size M", "in size M", "in M" — matches common clothing sizes
    size_match = re.search(
        r'(?:size\s+|in\s+size\s+|in\s+)(xxs|xs|xl|xxl|s\b|m\b|l\b'
        r'|w\d+(?:\s+l\d+)?|us\s*\d+(?:\.\d+)?|one size)',
        text,
    )
    size = size_match.group(1).strip().upper() if size_match else None

    # description: strip price/size clauses and common filler openers
    description = query
    if price_match:
        description = re.sub(
            r'(?:under|max|up to|below|for)\s*\$\d+(?:\.\d+)?'
            r'|\$\d+(?:\.\d+)?\s*(?:or less|max)',
            '', description, flags=re.IGNORECASE,
        )
    if size_match:
        description = re.sub(
            r'(?:size\s+|in\s+size\s+|in\s+)'
            r'(?:xxs|xs|xl|xxl|s|m|l|w\d+(?:\s+l\d+)?|us\s*\d+(?:\.\d+)?|one size)',
            '', description, flags=re.IGNORECASE,
        )
    description = re.sub(
        r"^(?:i'?m?\s+)?(?:looking for|trying to find|find me|want|need|searching for)"
        r'\s+(?:a\s+|an\s+)?',
        '', description.strip(), flags=re.IGNORECASE,
    )
    description = re.sub(r'^(?:a\s+|an\s+)', '', description.strip(), flags=re.IGNORECASE)
    description = description.strip(' ,.-') or query  # fallback to full query

    return {"description": description, "size": size, "max_price": max_price}


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict, style_tags: list | None = None) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    # Step 1: Initialize session
    session = _new_session(query, wardrobe)

    # Step 2: Parse query into description / size / max_price
    parsed = _parse_query(query)
    session["parsed"] = parsed

    # Step 3: Search listings — retry without size filter if first pass is empty
    results = search_listings(
        description=parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )

    if not results and parsed["size"] is not None:
        results = search_listings(
            description=parsed["description"],
            size=None,
            max_price=parsed["max_price"],
        )

    session["search_results"] = results

    if not results:
        price_hint = f" under ${parsed['max_price']:.0f}" if parsed["max_price"] else ""
        session["error"] = (
            f"No listings found for \"{parsed['description']}\"{price_hint}. "
            "Try different keywords or adjust your filters."
        )
        return session

    # Step 4: Select top result
    session["selected_item"] = results[0]

    # Step 4b: Compare price against similar listings
    session["price_verdict"] = compare_price(session["selected_item"])

    # Step 4c: Check trend activity for the item's style tags
    session["trend_report"] = get_trending_styles(session["selected_item"].get("style_tags", []))

    # Step 5: Suggest outfit — include session style tags if any have accumulated
    style_context = ""
    if style_tags:
        style_context = "tends toward " + ", ".join(style_tags[:10])

    session["outfit_suggestion"] = suggest_outfit(
        new_item=session["selected_item"],
        wardrobe=session["wardrobe"],
        style_context=style_context,
    )

    # Step 6: Generate fit card from outfit and selected item
    session["fit_card"] = create_fit_card(
        outfit=session["outfit_suggestion"],
        new_item=session["selected_item"],
    )

    # Step 7: Return completed session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
