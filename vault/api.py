"""Pokemon TCG API client."""

import time
from typing import Optional

import requests

API_BASE = "https://api.pokemontcg.io/v2"
API_KEY = "5ac12830-5a7b-4ee2-b048-1fa9d30c0522"

# Rate limiting: 1000 requests/day on free tier
# We'll track calls per session and add delays
_call_count = 0
_last_call_time = 0
MIN_CALL_INTERVAL = 0.1  # 100ms between calls


def _rate_limit() -> None:
    """Apply rate limiting between API calls."""
    global _last_call_time
    now = time.time()
    elapsed = now - _last_call_time
    if elapsed < MIN_CALL_INTERVAL:
        time.sleep(MIN_CALL_INTERVAL - elapsed)
    _last_call_time = time.time()


def _make_request(endpoint: str, params: Optional[dict] = None) -> dict:
    """Make an authenticated request to the API."""
    global _call_count
    _rate_limit()

    headers = {"X-Api-Key": API_KEY}
    url = f"{API_BASE}/{endpoint}"

    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    _call_count += 1

    return response.json()


def search_card(name: str, set_name: Optional[str] = None, number: Optional[str] = None) -> Optional[dict]:
    """
    Search for a card by name, set, and number.
    Returns the best match or None if not found.
    """
    # Build query
    query_parts = []

    # Clean up name - remove special chars that might break query
    clean_name = name.replace('"', '\\"').replace("'", "")
    query_parts.append(f'name:"{clean_name}"')

    if set_name:
        # Try to match set name
        clean_set = set_name.replace('"', '\\"').replace("'", "")
        query_parts.append(f'set.name:"{clean_set}"')

    if number:
        query_parts.append(f'number:"{number}"')

    query = " ".join(query_parts)

    try:
        result = _make_request("cards", {"q": query, "pageSize": 5})
        cards = result.get("data", [])

        if not cards:
            # Try a looser search with just the name
            result = _make_request("cards", {"q": f'name:"{clean_name}"', "pageSize": 10})
            cards = result.get("data", [])

        if cards:
            # If we have a number, try to find exact match
            if number:
                for card in cards:
                    if card.get("number") == number:
                        return card
            # Return first match
            return cards[0]

    except requests.RequestException:
        return None

    return None


def get_card_by_id(card_id: str) -> Optional[dict]:
    """Get a card by its API ID."""
    try:
        result = _make_request(f"cards/{card_id}")
        return result.get("data")
    except requests.RequestException:
        return None


def get_card_price(card: dict) -> Optional[float]:
    """
    Extract the market price from a card object.
    Prefers TCGPlayer market price, falls back to cardmarket.
    """
    tcgplayer = card.get("tcgplayer", {})
    prices = tcgplayer.get("prices", {})

    # Try different price categories in order of preference
    for price_type in ["holofoil", "reverseHolofoil", "normal", "1stEditionHolofoil", "1stEditionNormal"]:
        if price_type in prices:
            price_data = prices[price_type]
            # Prefer market price, then mid, then low
            for key in ["market", "mid", "low"]:
                if price_data.get(key):
                    return price_data[key]

    # Fallback to cardmarket
    cardmarket = card.get("cardmarket", {})
    cm_prices = cardmarket.get("prices", {})
    if cm_prices.get("averageSellPrice"):
        return cm_prices["averageSellPrice"]
    if cm_prices.get("trendPrice"):
        return cm_prices["trendPrice"]

    return None


def lookup_and_price_card(
    name: str,
    set_name: Optional[str] = None,
    number: Optional[str] = None,
    existing_api_id: Optional[str] = None
) -> tuple[Optional[str], Optional[float]]:
    """
    Look up a card and get its current price.
    Returns (api_id, price) tuple.
    """
    card = None

    # If we have an existing API ID, use it directly
    if existing_api_id:
        card = get_card_by_id(existing_api_id)

    # Otherwise search for the card
    if not card:
        card = search_card(name, set_name, number)

    if not card:
        return None, None

    api_id = card.get("id")
    price = get_card_price(card)

    return api_id, price


def get_call_count() -> int:
    """Get the number of API calls made this session."""
    return _call_count
