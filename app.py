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

def handle_query(user_query: str, wardrobe_choice: str) -> tuple[str, str, str, str]:
    """
    Called by Gradio when the user submits a query.

    Args:
        user_query:      The text the user typed into the search box.
        wardrobe_choice: Either "Example wardrobe" or "Empty wardrobe (new user)".

    Returns:
        A tuple of four strings:
            (listing_text, outfit_suggestion, fit_card, price_text)
        Each string maps to one of the four output panels in the UI.
    """
    # Guard empty query
    if not user_query or not user_query.strip():
        return "Please enter a search query.", "", "", ""

    # Select wardrobe based on radio choice
    wardrobe = (
        get_example_wardrobe()
        if wardrobe_choice == "Example wardrobe"
        else get_empty_wardrobe()
    )

    # Run the planning loop
    session = run_agent(user_query.strip(), wardrobe)

    # Surface error in first panel if the agent exited early
    if session["error"]:
        return session["error"], "", "", ""

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

    return listing_text, session["outfit_suggestion"], session["fit_card"], price_text


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

        outputs = [listing_output, outfit_output, fitcard_output, price_output]

        submit_btn.click(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=outputs,
        )
        query_input.submit(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=outputs,
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch()
