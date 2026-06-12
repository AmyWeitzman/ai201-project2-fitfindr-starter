# FitFindr

FitFindr is an AI agent that helps users find secondhand clothing and build outfits around new thrifted finds. You describe what you're looking for, and the agent searches a mock listings dataset, suggests a full outfit using your wardrobe, and generates a shareable social media caption.

## Dataset Overview

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

`data/wardrobe_schema.json` defines the format the agent uses to represent a user's existing wardrobe. It includes an example wardrobe with 10 items for testing and an empty wardrobe template for new users.

```python
from utils.data_loader import load_listings, get_example_wardrobe, get_empty_wardrobe

listings = load_listings()
wardrobe = get_example_wardrobe()   # 10-item sample wardrobe
empty    = get_empty_wardrobe()     # blank starting template
```

---

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root with your Groq API key (free at [console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

## Running the App

```bash
python app.py
```

Opens a Gradio web UI at `http://localhost:7860`. Type a query like "vintage graphic tee under $30" and select a wardrobe option.

To test the agent loop directly in the terminal without the UI:

```bash
python agent.py
```

---

## Tool Inventory

### `search_listings(description, size, max_price)`

**Purpose:** Searches the mock listings dataset for secondhand items matching a text description, with optional filters for size and price.

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `description` | `str` | Keywords describing the item (e.g. "vintage graphic tee") |
| `size` | `str \| None` | Size to filter by, case-insensitive substring match. `None` skips size filtering. |
| `max_price` | `float \| None` | Maximum price inclusive. `None` skips price filtering. |

**Output:** A `list[dict]` of matching listing dicts sorted by relevance score (highest first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns an empty list if nothing matches instead of raising an exception.

**Note:** Each listing is scored by how many keywords from the description appear in its title, description text, and style tags combined. Listings with a score of zero are dropped before sorting.

---

### `suggest_outfit(new_item, wardrobe)`

**Purpose:** Uses an LLM to suggest 1–2 complete outfit combinations for a listing item. Branches based on whether the user has a wardrobe set up.

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `new_item` | `dict` | A listing dict returned by `search_listings` |
| `wardrobe` | `dict` | A dict with an `'items'` key containing wardrobe item dicts. Can be empty. |

**Output:** A non-empty string with outfit suggestions. If `wardrobe['items']` is empty, returns general styling advice instead of wardrobe-specific combinations.

---

### `create_fit_card(outfit, new_item)`

**Purpose:** Uses an LLM to generate a short, shareable OOTD caption for the thrifted find. Uses a higher temperature (`1.2`) so outputs vary across runs.

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `outfit` | `str` | The outfit suggestion string from `suggest_outfit` |
| `new_item` | `dict` | The listing dict for the item |

**Output:** A 2–4 sentence string written in a casual voice that mentions the item name, price, and listing platform. If `outfit` is empty, returns a descriptive error string without calling the LLM.

---

### `compare_price(item)`

**Purpose:** Estimates whether a listing's price is fair by comparing it against similar items in the dataset. "Similar" means same category with at least one overlapping style tag.

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `item` | `dict` | A listing dict (e.g., `session["selected_item"]`) |

**Output:** A dict with the following fields:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `verdict` | `str` | `"great deal"`, `"fair price"`, `"a bit high"`, or `"no comparison available"` |
| `item_price` | `float` | The listing's price |
| `avg_price` | `float \| None` | Average price across comparable listings |
| `min_price` | `float \| None` | Cheapest comparable |
| `max_price` | `float \| None` | Most expensive comparable |
| `comparable_count` | `int` | Number of comparable listings found |
| `summary` | `str` | Human-readable one-line summary |

Verdict thresholds: below 80% of the average -> `"great deal"`, above 120% -> `"a bit high"`, otherwise `"fair price"`. Never raises an exception - if no comparables exist, returns `"no comparison available"` with `None` price fields.

---

## Planning Loop

1. **Parse the query** using regex to extract a `description`, `size` (if mentioned), and `max_price` (if mentioned). Filler phrases like "I'm looking for" are stripped so the search gets clean keywords.

2. **Search listings** with the parsed parameters. If the first search returns nothing and a size was specified, the agent retries once without the size filter (in case the user's size isn't listed exactly). If still empty, the agent sets `session["error"]` and returns early — `suggest_outfit` is never called with empty input.

3. **Select the top result** (`results[0]`) and store it in the session as `selected_item`.

4. **Compare the price** against similar listings in the dataset. Stored in `session["price_verdict"]`. This step always completes - a "no comparison available" result is stored if no comparables exist.

5. **Suggest an outfit** using the selected item and the user's wardrobe.

6. **Generate a fit card** using the outfit suggestion and the selected item.

7. **Return the session dict.** The caller checks `session["error"]` first to know whether the interaction succeeded.

The key branching condition is after step 2: if `search_results` is empty, the loop exits immediately. This means the agent's behavior is visibly different for a query that matches listings versus one that doesn't.

---

## State Management

All data produced during a run lives in a single session dict initialized at the start of `run_agent()`:

```python
session = {
    "query": "<original user message>",
    "parsed": {"description": ..., "size": ..., "max_price": ...},
    "search_results": [...],
    "selected_item": None,
    "wardrobe": {...},
    "outfit_suggestion": None,
    "fit_card": None,
    "error": None,
}
```

Each step reads from this dict and writes its result back to it. `suggest_outfit` receives `session["selected_item"]` and `session["wardrobe"]` directly - the same objects, not copies. `create_fit_card` receives `session["outfit_suggestion"]` and `session["selected_item"]`. Nothing is re-computed or re-fetched between steps.

---

## Error Handling

| Tool | Failure mode | What the agent does |
| ---- | ------------ | ------------------- |
| `search_listings` | No listings match the query | Retries once without the size filter. If still empty, sets `session["error"]` with a message like `"No listings found for "designer ballgown" under $5. Try different keywords or adjust your filters."` and returns without calling the other tools. |
| `suggest_outfit` | Wardrobe is empty | Skips the wardrobe-specific prompt and asks the LLM for general styling advice instead. Does not raise an exception or return an empty string. |
| `create_fit_card` | Outfit input is missing or incomplete | Returns `"Couldn't generate a fit card — no outfit suggestion was provided."` immediately, without making an LLM API call. |

**Concrete examples from testing:**

- Running `search_listings("designer ballgown", size="XXS", max_price=5)` returned `[]` — the agent correctly surfaced `"No listings found for "designer ballgown" under $5..."` in `session["error"]` and left `fit_card` as `None`.
- Running `suggest_outfit(results[0], get_empty_wardrobe())` with an empty wardrobe returned a full general styling response (two outfit ideas based on the item's vibe) rather than crashing.
- Running `create_fit_card("", results[0])` returned the error string immediately — confirmed by a test that asserts `_get_groq_client` is never called in this case.

---

## Spec Reflection

The implementation matched the planning spec closely. A few things worth noting:

**What went as planned:** The three-tool pipeline, the early-exit branch on empty search results, the empty-wardrobe fallback in `suggest_outfit`, and the session dict structure all ended up exactly as described in `planning.md`. The architecture diagram's error lane pattern (all errors returning to a single path) translated directly into the `session["error"]` + early return pattern in code.

**One thing that needed to be added:** Query parsing wasn't fully specced out in `planning.md` beyond "extract description, size, max_price." In practice this required writing a regex parser (`_parse_query`) that handles several natural language patterns ("under $30", "in size M", "I'm looking for..."). That ended up being its own function with its own edge cases.

**One thing that worked better than expected:** The `suggest_outfit` empty-wardrobe branch. The general styling advice the LLM returns when there's no wardrobe is genuinely useful. It describes what kinds of pieces pair well with the item rather than just saying "no wardrobe available."

---

## AI Tool Usage

### Instance 1 — Implementing the three tools in `tools.py`

**What I gave Claude Code:** The Tool 1, Tool 2, and Tool 3 spec blocks from `planning.md` (what each tool does, input parameters with types, return value, failure mode), plus the `load_listings()` function signature from `data_loader.py` for context on Tool 1, and the existing Groq client setup already in `tools.py` for Tools 2 and 3.

**What it produced:** Complete implementations of all three functions matching the spec signatures. The keyword scoring logic in `search_listings` used a set intersection approach, counting how many query keywords appeared in the listing's combined text fields. `suggest_outfit` correctly branched on empty vs. non-empty wardrobe. `create_fit_card` had the guard clause for empty outfit strings.

**What I reviewed and changed:** I verified the function signatures matched my spec exactly before running anything. The `create_fit_card` temperature was set to `0.7` in the initial output. I increased it to `1.2` to get more caption variety. I also confirmed the `search_listings` size filter used case-insensitive substring matching (so "M" matches "S/M") rather than exact equality.

---

### Instance 2 — Implementing the planning loop in `agent.py`

**What I gave Claude Code:** The Architecture diagram from `planning.md` (the ASCII flowchart showing the Planning Loop container, tool branches, session state updates, and error lane), the Planning Loop section (the numbered steps and early-exit conditions), and the State Management section (the session dict structure).

**What it produced:** A complete `run_agent()` implementation with `_parse_query()` as a separate helper. The fallback retry (dropping the size filter on empty results) was included because it was shown in the diagram. State was written back to the session dict at each step. The early return after empty search results meant `suggest_outfit` was never called unconditionally.

**What I reviewed and changed:** I checked that the session dict keys in the generated code matched the keys initialized in `_new_session()` exactly. I also ran both the happy path and the no-results path from the CLI test at the bottom of `agent.py` to confirm the branching actually worked - the no-results case returned an error message with `fit_card` still `None`, which confirmed the agent wasn't calling all three tools regardless of what `search_listings` returned.
