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
    size=None,
    max_price=None,
):
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

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    if max_price is not None:
        listings = [l for l in listings if l["price"] <= max_price]

    if size is not None:
        listings = [l for l in listings if size.lower() in l["size"].lower()]

    keywords = description.lower().split()

    scored = []
    for listing in listings:
        text = " ".join([
            listing.get("title", ""),
            listing.get("description", ""),
            listing.get("category", ""),
            " ".join(listing.get("style_tags", [])),
            " ".join(listing.get("colors", [])),
            listing.get("brand", "") or "",
        ]).lower()

        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scored.append((score, listing))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [listing for _, listing in scored]


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
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    client = _get_groq_client()
    wardrobe_items = wardrobe.get("items", [])

    item_desc = (
        f"Title: {new_item.get('title', 'Unknown item')}\n"
        f"Category: {new_item.get('category', '')}\n"
        f"Colors: {', '.join(new_item.get('colors', []))}\n"
        f"Style tags: {', '.join(new_item.get('style_tags', []))}"
    )

    if not wardrobe_items:
        prompt = (
            f"A shopper is considering buying this thrifted item:\n{item_desc}\n\n"
            "Their wardrobe is empty, so suggest general styling ideas for this item: "
            "what kinds of pieces pair well with it, what vibe or aesthetic it suits, "
            "and how to wear it. Keep it practical and specific."
        )
    else:
        wardrobe_lines = []
        for w in wardrobe_items:
            line = (
                f"- {w.get('name', 'Item')} ({w.get('category', '')}): "
                f"colors {', '.join(w.get('colors', []))}, "
                f"tags {', '.join(w.get('style_tags', []))}"
            )
            if w.get("notes"):
                line += f", notes: {w['notes']}"
            wardrobe_lines.append(line)

        wardrobe_text = "\n".join(wardrobe_lines)
        prompt = (
            f"A shopper is considering buying this thrifted item:\n{item_desc}\n\n"
            f"Their current wardrobe includes:\n{wardrobe_text}\n\n"
            "Suggest 1-2 complete outfits pairing the new item with specific named pieces "
            "from their wardrobe. Be concrete about which items to combine and why they work together."
        )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
        )
        result = (response.choices[0].message.content or "").strip()
        if result:
            return result
    except Exception:
        pass

    return (
        f"This {new_item.get('title', 'item')} would work great styled casually — "
        "try pairing it with neutral basics, layering with a light jacket, "
        "and finishing with simple footwear to let the piece stand out."
    )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return "Error: no outfit suggestion provided — run suggest_outfit first to generate styling ideas."

    client = _get_groq_client()

    title = new_item.get("title", "this find")
    price = new_item.get("price", "")
    platform = new_item.get("platform", "a thrift app")
    price_str = f"${price:.2f}" if isinstance(price, (int, float)) else str(price)

    prompt = (
        f"Write a 2-4 sentence Instagram/TikTok caption for someone who thrifted this item:\n"
        f"Item: {title}\n"
        f"Price: {price_str}\n"
        f"Platform: {platform}\n\n"
        f"Outfit they styled it with:\n{outfit}\n\n"
        "Guidelines:\n"
        "- Sound like a real person posting their OOTD, not a product ad\n"
        "- Mention the item name, price, and platform each exactly once, woven in naturally\n"
        "- Capture the specific vibe of the outfit\n"
        "- Keep it casual and authentic"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=1.0,
        )
        result = (response.choices[0].message.content or "").strip()
        if result:
            return result
    except Exception:
        pass

    return (
        f"snagged this {title} off {platform} for {price_str} and honestly couldn't be happier 🖤 "
        "styled it up and it fits the vibe perfectly — sometimes thrifting just hits different."
    )
