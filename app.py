"""
app.py

Gradio interface for FitFindr. The layout and wiring are already set up —
your job is to fill in handle_query() so it calls run_agent() and maps
the session results to the three output panels.

Run with:
    python app.py

Then open the localhost URL shown in your terminal (usually http://localhost:7860,
but check your terminal — the port may differ).
"""

import gradio as gr

from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── query handler ─────────────────────────────────────────────────────────────

def handle_query(
    user_query: str,
    wardrobe_choice: str,
    style_tags: list,
) -> tuple[str, str, str, str, list]:
    """
    Called by Gradio when the user submits a query.

    Args:
        user_query:     The text the user typed into the search box.
        wardrobe_choice: Either "Example wardrobe" or "Empty wardrobe (new user)".
        style_tags:     Accumulated style tags from earlier searches this session
                        (held in gr.State — starts empty, grows automatically).

    Returns:
        A tuple of four visible strings plus the updated style_tags state:
            (listing_text, outfit_suggestion, fit_card, price_text, updated_style_tags)
    """
    # Guard empty query
    if not user_query or not user_query.strip():
        return "Please enter a search query.", "", "", "", style_tags

    # Select wardrobe based on radio choice
    wardrobe = (
        get_example_wardrobe()
        if wardrobe_choice == "Example wardrobe"
        else get_empty_wardrobe()
    )

    # Run the planning loop, passing in whatever style tags have built up this session
    session = run_agent(user_query.strip(), wardrobe, style_tags=style_tags)

    # Surface error in first panel if the agent exited early
    if session["error"]:
        return session["error"], "", "", "", style_tags

    # Format the selected listing into readable text
    item = session["selected_item"]
    lines = [
        item["title"],
        "",
        f"Price:      ${item['price']:.2f}",
        f"Size:       {item['size']}",
        f"Condition:  {item['condition']}",
        f"Platform:   {item['platform']}",
        f"Colors:     {', '.join(item['colors'])}",
    ]
    if item.get("brand"):
        lines.append(f"Brand:      {item['brand']}")
    lines += ["", item["description"]]
    listing_text = "\n".join(lines)

    # Format the price verdict
    verdict = session["price_verdict"]
    if verdict["comparable_count"] == 0:
        price_text = verdict["summary"]
    else:
        emoji = {"great deal": "✅", "fair price": "✓", "a bit high": "⚠️"}.get(
            verdict["verdict"], ""
        )
        price_text = "\n".join([
            f"This item:    ${verdict['item_price']:.2f}",
            f"Avg similar:  ${verdict['avg_price']:.2f}",
            f"Range:        ${verdict['min_price']:.2f} – ${verdict['max_price']:.2f}",
            f"Comparables:  {verdict['comparable_count']} listing(s)",
            "",
            f"Verdict: {verdict['verdict'].title()} {emoji}",
        ])

    # Prepend fallback notice if filters were loosened
    fallbacks = session.get("search_fallbacks", [])
    if fallbacks:
        notice = "ℹ️ Adjusted search: " + "; ".join(fallbacks) + "."
        listing_text = notice + "\n\n" + listing_text

    # Append trend activity to the listing panel
    trend = session.get("trend_report")
    if trend and trend["matched_posts"]:
        trend_lines = ["", "─" * 40, "🔥 Trending now", trend["summary"], ""]
        for post in trend["matched_posts"]:
            age = f"{post['days_ago']}d ago"
            count = f"{post['post_count']:,} posts"
            trend_lines.append(f"[{post['platform']} · {count} · {age}]")
            trend_lines.append(f'"{post["caption"]}"')
            trend_lines.append("  " + "  ".join(post["hashtags"][:4]))
            trend_lines.append("")
        if trend["top_hashtags"]:
            trend_lines.append("Top tags: " + "  ".join(trend["top_hashtags"]))
        listing_text += "\n" + "\n".join(trend_lines)

    # Accumulate style tags from this search into session state
    updated_tags = sorted(set(style_tags) | set(item.get("style_tags", [])))[:20]

    return listing_text, session["outfit_suggestion"], session["fit_card"], price_text, updated_tags


# ── interface ─────────────────────────────────────────────────────────────────

EXAMPLE_QUERIES = [
    "vintage graphic tee under $30",
    "90s track jacket in size M",
    "flowy midi skirt under $40",
    "black combat boots size 8",
    "designer ballgown size XXS under $5",   # deliberate no-results test
]

def build_interface():
    with gr.Blocks(title="FitFindr") as demo:
        gr.Markdown("""
# FitFindr 🛍️
Find secondhand pieces and get outfit ideas based on your wardrobe.
Describe what you're looking for — include size and price if you want to filter.
        """)

        # Holds accumulated style tags for the duration of the browser session
        style_state = gr.State([])

        with gr.Row():
            query_input = gr.Textbox(
                label="What are you looking for?",
                placeholder="e.g. vintage graphic tee under $30, size M",
                lines=2,
                scale=3,
            )
            wardrobe_choice = gr.Radio(
                choices=["Example wardrobe", "Empty wardrobe (new user)"],
                value="Example wardrobe",
                label="Wardrobe",
                scale=1,
            )

        submit_btn = gr.Button("Find it", variant="primary")

        with gr.Row():
            listing_output = gr.Textbox(
                label="🛍️ Top listing found",
                lines=8,
                interactive=False,
            )
            outfit_output = gr.Textbox(
                label="👗 Outfit idea",
                lines=8,
                interactive=False,
            )
            fitcard_output = gr.Textbox(
                label="✨ Your fit card",
                lines=8,
                interactive=False,
            )
            price_output = gr.Textbox(
                label="💰 Price comparison",
                lines=8,
                interactive=False,
            )

        gr.Examples(
            examples=[[q, "Example wardrobe"] for q in EXAMPLE_QUERIES],
            inputs=[query_input, wardrobe_choice],
            label="Try these queries",
        )

        outputs = [listing_output, outfit_output, fitcard_output, price_output, style_state]

        submit_btn.click(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice, style_state],
            outputs=outputs,
        )
        query_input.submit(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice, style_state],
            outputs=outputs,
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch()
