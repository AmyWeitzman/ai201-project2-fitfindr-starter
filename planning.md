# FitFindr — planning.md

---

## Tools

### Tool 1: search_listings

**What it does:**
Searches the listings dataset for secondhand clothing items that match a text description along with optional filters for size and price.

**Input parameters:**

- `description` (str): Brief description of the item the user wants (e.g. "vintage graphic tee", "floral sleeveless dress")
- `size` (str | None): Clothing size to filter by (or None to skip size filtering)
- `max_price` (float | None): Maximum price the user is willing to pay (inclusive) (or None to skip price filtering)

**What it returns:**
A list of listing dicts sorted by relevance score (highest first). Each dict has the following fields:

- `id` — unique listing identifier
- `title` — item name
- `description` — item description
- `category` — clothing category (e.g. tops, bottoms)
- `style_tags` — list of style keywords (e.g. ["vintage", "streetwear"])
- `size` — size string (ex: S/M, W30 L30)
- `condition` — item condition (e.g. "like new", "good")
- `price` — float, listed price for item
- `colors` — list of color strings
- `brand` — clothing brand name
- `platform` — platform the item is listed on (e.g. Depop, Poshmark)

Returns an empty list if nothing matches, does not raise an exception.

**What happens if it fails or returns nothing:**
The agent first tries a fallback search by dropping the size filter (in case the user's size isn't listed exactly). If that still returns nothing, the agent tells the user no matches were found and asks them to try again with different keywords or adjust their filters.

---

### Tool 2: suggest_outfit

**What it does:**
Takes a listing item the user is considering and their existing wardrobe and uses an LLM to suggest a full outfit combination.

**Input parameters:**

- `new_item` (dict): A listing dict returned by `search_listings` 
- `wardrobe` (dict): A dict with an `'items'` key containing a list of wardrobe item dicts

**What it returns:**
An outfit suggestion as a string. If wardrobe is not empty, suggestions will include specific items from the wardrobe. If the wardrobe is empty, the response will describe what kinds of items the new item pairs well with.

**What happens if it fails or returns nothing:**
If the wardrobe is empty, the agent just returns general styling advice using just the item details. If the LLM call itself fails (e.g. bad API key or network error), the agent catches the exception and tells the user the outfit suggestion step failed, and then asks if they'd like to try again.

---

### Tool 3: create_fit_card

**What it does:**
Takes the outfit suggestion and the new item's details and uses an LLM to generate a short, shareable caption that is suitable to post on social media. 

**Input parameters:**

- `outfit` (str): The outfit suggestion string returned by `suggest_outfit`
- `new_item` (dict): The listing dict for the new item

**What it returns:**
A brief (few sentences) caption based on the outfit written in a casual, upbeat tone

**What happens if it fails or returns nothing:**
If `outfit` is empty or the LLM call fails, the function should return a descriptive error message so the agent can relay it to the user

---

### Additional Tools (if any)

N/A

---

## Planning Loop

The agent starts by extracting the relevant info from the user's query: description, size (if mentioned), max price (if mentioned). It then runs through the three tools in sequence, passing outputs from one as inputs to the next along with additional info such as the user's wardrobe.

At each step it checks whether the previous tool returned usable data before moving on:

1. Call `search_listings`. If the result is empty, try once without the size filter. If still empty, stop and ask the user to adjust their query.
2. If Step 1 has a result, take the top listing and call `suggest_outfit` with it and the user's wardrobe. If this returns an empty string, stop and tell the user.
3. If Step 2 returns an outfit suggestion, call `create_fit_card` with the outfit and the listing. Return the fit card to the user.

The loop knows it's done when either a fit card is successfully returned, or an early exit condition is hit (no listings found, no outfit possible).

---

## State Management

State is stored in a dictionary that the agent updates up as tools run. It starts empty and gets populated as each tool returns a result. Each tool call reads from this dict and writes its result back to it. For instance, `suggest_outfit` needs both `top_listing` and `wardrobe`. `create_fit_card` needs both `outfit_suggestion` and `top_listing`.

Example of state dict:
```python
session = {
    "query": "<original user message>",
    "top_listing": "<first result from search_listings>",
    "outfit_suggestion": "<string from suggest_outfit>",
    "fit_card": "<string from create_fit_card>",
    "wardrobe": "<user's wardrobe dict>"
}
```

---

## Error Handling

| Tool | Failure mode | Agent response |
| ------ | ----------- | ---------------- |
| search_listings | No results match the query | Retry once without the size filter. If still empty, tell the user no matches were found and ask them to try different keywords or filters. |
| suggest_outfit | Wardrobe is empty | Skip wardrobe-based suggestions and ask the LLM for general styling advice for the item instead. |
| create_fit_card | Outfit input is missing or incomplete | Return a descriptive error string (e.g. "Couldn't generate a fit card - no outfit suggestion was provided.") without raising an exception. |

---

## Architecture

```text
User query
    │
    ▼
Planning Loop ────────────────────────────────────────────┐
    │                                                     │
    ├─► search_listings(description, size, max_price)     │
    │       │ results=[]                                  │
    │       ├──► retry without size filter                │
    │       │       │ still empty                         │
    │       │       ├──► [ERROR] "No listings found" ─────┤
    │       │                                             │
    │       │ results=[item, ...]                         │
    │       ▼                                             │
    │   Session: top_listing = results[0]                 │
    │       │                                             │
    ├─► suggest_outfit(top_listing, wardrobe)             │
    │       │ outfit=""                                   │
    │       ├──► [ERROR] "Can't suggest an outfit" ───────┤
    │       │                                             │
    │   Session: outfit_suggestion = "..."                │
    │       │                                             │
    └─► create_fit_card(outfit_suggestion, top_listing)   │
            │ outfit missing/empty                        │
            ├──► [ERROR] "Couldn't generate fit card" ────┤
            │                                             │
        Session: fit_card = "..."                         │
            │                                             └─ error paths return here
            ▼
        Return session
```


---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

I'll use Claude Code (the CLI) for all three tools, feeding it one tool at a time.

- **search_listings**: I'll give Claude the Tool 1 section of this doc (inputs, return fields, failure behavior) plus the `load_listings()` signature from `data_loader.py` and ask it to implement the keyword scoring and filtering logic. I'll verify by running it against three manual test queries (one that should match, one with a price too low to match anything, and one with an non-standard size)  and checking the returned list looks right before wiring it into the agent.

- **suggest_outfit**: I'll give Claude the Tool 2 section of this doc plus the Groq client setup already in `tools.py` and ask it to implement both branches (empty wardrobe -> general advice, non-empty wardrobe -> specific outfit combos). I'll verify by calling it directly with a fake listing and an empty wardrobe, then again with a wardrobe that has a few items, and reading the LLM responses to make sure they make sense and aren't empty.

- **create_fit_card**: I'll give Claude the Tool 3 section of this doc and ask it to implement the guard clause for an empty outfit string, then the prompt and LLM call. I'll verify by calling it with a real listing and a sample outfit string and making sure the output reads like something one would actually post, and by calling it with an empty outfit string to confirm it returns an error message rather than crashing.

**Milestone 4 — Planning loop and state management:**

I'll give Claude the Architecture diagram, the State Management section, and the Planning Loop section from this doc and ask it to implement the agent loop in `agent.py`. I'll verify it end-to-end by running a full interaction using the example query below and checking that the right tool is called at each step, state is passed correctly between calls, and the fallback path triggers when I give it an impossible query.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The agent should call the `search_listings` tool, passing in info from the user's query as arguments matching the signature of the function. Ex: `search_listings('vintage graphic tee', max_price=30)`

**Step 2:**
If Step 1 returns a listing, the agent should then call the `suggest_outfit` tool, passing in info from that listing and the user's wardrobe. Ex: `suggest_outfit(new_item=<listing from step 1>, wardrobe=<user's wardrobe>)`. If Step 1 does not return a listing, the agent should first try a fallback strategy, such as being less restrictive on the search criteria by removing the size parameter, and if that isn't successful in finding a match either, the agent should respond to the user saying they couldn't find a match and prompt user to try again with a different query.

**Step 3:**
If Step 2 returns an outfit, the agent should then call the `create_fit_card` tool, passing in info from that outfit. Ex: `create_fit_card(outfit=<outfit from step 2>, new_item=<listing from step 1>)`. If Step 2 does not return an outfit, the agent should tell the user they can't find a matching outfit given their wardrobe.

**Final output to user:**
If all the tools run successfully, the user should see a new clothing item suggestion, suggested ways to make a whole outfit with that item based on their wardrobe, and a brief description that is suitable for a social media post.
