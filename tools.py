"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform
    """
    listings = load_listings()

    if max_price is not None:
        listings = [l for l in listings if l["price"] <= max_price]

    if size is not None:
        listings = [l for l in listings if size.lower() in l["size"].lower()]

    keywords = set(description.lower().split())

    def score(listing):
        searchable = " ".join([
            listing["title"].lower(),
            listing["description"].lower(),
            " ".join(tag.lower() for tag in listing["style_tags"]),
        ])
        return sum(1 for kw in keywords if kw in searchable)

    scored = [(score(l), l) for l in listings]
    scored = [(s, l) for s, l in scored if s > 0]
    scored.sort(key=lambda x: x[0], reverse=True)

    return [l for _, l in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offers general styling advice for the item
        rather than raising an exception or returning an empty string.
    """
    client = _get_groq_client()

    item_summary = (
        f"{new_item['title']} — {new_item['category']}, size {new_item['size']}, "
        f"${new_item['price']}\n"
        f"Style tags: {', '.join(new_item['style_tags'])}\n"
        f"Colors: {', '.join(new_item['colors'])}"
    )

    wardrobe_items = wardrobe.get("items", [])

    if not wardrobe_items:
        prompt = (
            "You're a fashion stylist. A user is considering this thrifted find:\n\n"
            f"{item_summary}\n\n"
            "They haven't set up their wardrobe yet. Describe 1–2 outfit ideas "
            "in general terms — what types of pieces pair well with this item, "
            "what vibe it suits, and how to wear it."
        )
    else:
        wardrobe_lines = "\n".join(
            f"- {item['name']} ({item['category']}, colors: {', '.join(item['colors'])})"
            for item in wardrobe_items
        )
        prompt = (
            "You're a fashion stylist. A user is considering this thrifted find:\n\n"
            f"{item_summary}\n\n"
            "Here's what they already own:\n"
            f"{wardrobe_lines}\n\n"
            "Suggest 1–2 complete outfit combinations using the new item and "
            "specific named pieces from their wardrobe."
        )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, returns a descriptive error message
        string — does NOT raise an exception.

    The caption:
    - Feels casual and authentic (like a real OOTD post)
    - Mentions the item name, price, and platform naturally (once each)
    - Captures the outfit vibe in specific terms
    - Varies across runs (uses higher LLM temperature)
    """
    if not outfit or not outfit.strip():
        return "Couldn't generate a fit card — no outfit suggestion was provided."

    client = _get_groq_client()

    prompt = (
        "Write a 2–4 sentence Instagram/TikTok OOTD caption for this thrifted find.\n\n"
        f"Item: {new_item['title']}\n"
        f"Price: ${new_item['price']}\n"
        f"Platform: {new_item['platform']}\n"
        f"Outfit: {outfit}\n\n"
        "Rules:\n"
        "- Sound casual and authentic — like something a real person would actually post\n"
        "- Mention the item name, price, and platform once each, worked in naturally\n"
        "- Describe the outfit vibe in specific terms, not generic phrases\n"
        "- Keep it under 4 sentences"
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=1.2,
    )
    return response.choices[0].message.content
