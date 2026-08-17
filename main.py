import json
import math
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


CITIES = {
    "Sydney": (-33.8688, 151.2093, "Australia/Sydney"),
    "New York City": (40.7128, -74.0060, "America/New_York"),
    "London": (51.5074, -0.1278, "Europe/London"),
    "Munich": (48.1351, 11.5820, "Europe/Berlin"),
    "Hong Kong": (22.3193, 114.1694, "Asia/Hong_Kong"),
    "Chengdu": (30.5728, 104.0668, "Asia/Shanghai"),
}

# This is deliberately a conservative research-only heuristic.
# It is NOT a calibrated probability model and does not place trades.
MODEL_SIGMA_C = 1.5
MIN_EDGE = 0.10


def get_weather(latitude, longitude, timezone):
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,apparent_temperature",
        "hourly": "temperature_2m",
        "forecast_days": 3,
        "timezone": timezone,
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def search_polymarket():
    url = "https://gamma-api.polymarket.com/public-search"

    params = {
        "q": "weather",
        "limit_per_type": 100,
        "search_profiles": "false",
        "search_tags": "false",
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def parse_prices(market):
    outcomes = market.get("outcomes")
    prices = market.get("outcomePrices")

    try:
        outcomes = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
        prices = json.loads(prices) if isinstance(prices, str) else prices
    except (json.JSONDecodeError, TypeError):
        return {}

    if not outcomes or not prices:
        return {}

    result = {}
    for outcome, price in zip(outcomes, prices):
        try:
            result[str(outcome).strip().lower()] = float(price)
        except (TypeError, ValueError):
            continue
    return result


def detect_city(question):
    question_lower = question.lower()
    for city in CITIES:
        if city.lower() in question_lower:
            return city
    return None


def parse_temperature_condition(question):
    q = question.lower().replace("°", "")

    # Exact temperature, e.g. "be 26c"
    exact = re.search(r"\b(\d+(?:\.\d+)?)\s*c\b", q)
    if exact:
        target = float(exact.group(1))
        if "or below" in q or "or lower" in q or "or less" in q:
            return "at_or_below", target
        if "or higher" in q or "or above" in q:
            return "at_or_above", target
        return "exact", target

    # Fahrenheit markets are supported for NYC-style questions.
    exact_f = re.search(r"\b(\d+(?:\.\d+)?)\s*f\b", q)
    if exact_f:
        target = (float(exact_f.group(1)) - 32) * 5 / 9
        if "or below" in q or "or lower" in q or "or less" in q:
            return "at_or_below", target
        if "or higher" in q or "or above" in q:
            return "at_or_above", target
        return "exact", target

    between = re.search(r"between\s+(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*f", q)
    if between:
        low = (float(between.group(1)) - 32) * 5 / 9
        high = (float(between.group(2)) - 32) * 5 / 9
        return "range", (low, high)

    between_c = re.search(r"between\s+(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*c", q)
    if between_c:
        return "range", (float(between_c.group(1)), float(between_c.group(2)))

    return None, None


def parse_market_date(question, timezone):
    match = re.search(r"on\s+([A-Za-z]+\s+\d{1,2})", question)
    if not match:
        return None

    local_now = datetime.now(ZoneInfo(timezone))
    text = f"{match.group(1)} {local_now.year}"

    try:
        return datetime.strptime(text, "%B %d %Y").date()
    except ValueError:
        try:
            return datetime.strptime(text, "%b %d %Y").date()
        except ValueError:
            return None


def forecast_max_for_date(weather, target_date, timezone):
    hourly = weather.get("hourly", {})
    times = hourly.get("time", [])
    temperatures = hourly.get("temperature_2m", [])

    pairs = []
    for time_text, temperature in zip(times, temperatures):
        try:
            local_dt = datetime.fromisoformat(time_text).replace(tzinfo=ZoneInfo(timezone))
            if local_dt.date() == target_date:
                pairs.append((float(temperature), time_text))
        except (TypeError, ValueError):
            continue

    if not pairs:
        return None

    return max(pairs, key=lambda item: item[0])


def normal_cdf(x, mean, sigma):
    return 0.5 * (1 + math.erf((x - mean) / (sigma * math.sqrt(2))))


def estimate_probability(condition, target, forecast_max):
    if forecast_max is None:
        return None

    if condition == "exact":
        # Approximate probability of a rounded daily maximum landing on target.
        upper = normal_cdf(target + 0.5, forecast_max, MODEL_SIGMA_C)
        lower = normal_cdf(target - 0.5, forecast_max, MODEL_SIGMA_C)
        return max(0.0, min(1.0, upper - lower))

    if condition == "at_or_below":
        return normal_cdf(target + 0.5, forecast_max, MODEL_SIGMA_C)

    if condition == "at_or_above":
        return 1 - normal_cdf(target - 0.5, forecast_max, MODEL_SIGMA_C)

    if condition == "range":
        low, high = target
        return normal_cdf(high + 0.5, forecast_max, MODEL_SIGMA_C) - normal_cdf(
            low - 0.5, forecast_max, MODEL_SIGMA_C
        )

    return None


def analyze_market(question, market, weather_by_city):
    city = detect_city(question)
    if not city:
        return None

    latitude, longitude, timezone = CITIES[city]
    condition, target = parse_temperature_condition(question)
    if condition is None:
        return None

    market_date = parse_market_date(question, timezone)
    if market_date is None:
        return None

    weather = weather_by_city.get(city)
    if weather is None:
        weather = get_weather(latitude, longitude, timezone)
        weather_by_city[city] = weather

    forecast = forecast_max_for_date(weather, market_date, timezone)
    if forecast is None:
        return None

    forecast_max, forecast_time = forecast
    probability = estimate_probability(condition, target, forecast_max)
    prices = parse_prices(market)

    yes_price = prices.get("yes")
    no_price = prices.get("no")

    if probability is None or yes_price is None:
        return None

    yes_edge = probability - yes_price
    no_edge = (1 - probability) - no_price if no_price is not None else None

    return {
        "city": city,
        "date": str(market_date),
        "question": question,
        "forecast_max": forecast_max,
        "forecast_time": forecast_time,
        "condition": condition,
        "target": target,
        "model_probability": probability,
        "yes_price": yes_price,
        "no_price": no_price,
        "yes_edge": yes_edge,
        "no_edge": no_edge,
    }


def print_analysis(result):
    print()
    print(f"{result['city'].upper()} — {result['date']}")
    print("-" * 50)
    print("Market:", result["question"])
    print(f"Forecast daily max: {result['forecast_max']:.1f} °C")
    print("Forecast peak:", result["forecast_time"])
    print(f"YES price: {result['yes_price']:.3f}")
    if result["no_price"] is not None:
        print(f"NO price: {result['no_price']:.3f}")
    print(f"Model estimate: {result['model_probability']:.1%}")
    print(f"YES edge: {result['yes_edge']:+.1%}")
    if result["no_edge"] is not None:
        print(f"NO edge: {result['no_edge']:+.1%}")

    if result["yes_edge"] >= MIN_EDGE:
        print("SIGNAL: POSSIBLE YES EDGE")
    elif result["no_edge"] is not None and result["no_edge"] >= MIN_EDGE:
        print("SIGNAL: POSSIBLE NO EDGE")
    else:
        print("SIGNAL: NO CLEAR EDGE")


def main():
    print("Polymarket Weather Bot V2")
    print("Multi-city market analyzer — research/paper trading only")

    print()
    print("Loading weather forecasts...")
    weather_by_city = {}

    for city, (latitude, longitude, timezone) in CITIES.items():
        try:
            weather = get_weather(latitude, longitude, timezone)
            weather_by_city[city] = weather
            current = weather["current"]
            print(
                f"{city}: {current['temperature_2m']} °C "
                f"(feels like {current['apparent_temperature']} °C)"
            )
        except requests.RequestException as exc:
            print(f"{city}: weather unavailable ({exc})")

    print()
    print("Searching Polymarket weather markets...")
    data = search_polymarket()
    events = data.get("events", [])

    analyzed = 0
    opportunities = 0

    for event in events:
        for market in event.get("markets", []):
            question = market.get("question")
            if not question or market.get("closed") is True:
                continue

            if not any(
                keyword in question.lower()
                for keyword in ["temperature", "weather", "rain", "snow", "hot", "cold"]
            ):
                continue

            try:
                result = analyze_market(question, market, weather_by_city)
            except requests.RequestException as exc:
                print(f"Weather request failed: {exc}")
                continue

            if result is None:
                continue

            analyzed += 1
            print_analysis(result)

            if result["yes_edge"] >= MIN_EDGE or (
                result["no_edge"] is not None and result["no_edge"] >= MIN_EDGE
            ):
                opportunities += 1

    print()
    print("ANALYSIS SUMMARY")
    print("----------------")
    print("Markets analyzed:", analyzed)
    print("Potential edges:", opportunities)
    print("Minimum edge threshold:", f"{MIN_EDGE:.0%}")
    print("Model sigma:", f"{MODEL_SIGMA_C:.1f} °C")
    print("No trades were executed.")


if __name__ == "__main__":
    main()
