import json
import requests


LATITUDE = -33.8688
LONGITUDE = 151.2093


def get_weather():
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "current": "temperature_2m,apparent_temperature",
        "hourly": "temperature_2m",
        "forecast_days": 2,
        "timezone": "Australia/Sydney",
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    return response.json()


def search_polymarket():
    url = "https://gamma-api.polymarket.com/public-search"

    params = {
        "q": "weather",
        "limit_per_type": 20,
        "search_profiles": "false",
        "search_tags": "false",
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    return response.json()


def main():
    print("Polymarket Weather Bot V1")
    print("Getting weather data...")

    weather = get_weather()

    current = weather["current"]
    hourly = weather["hourly"]

    temperatures = hourly["temperature_2m"]
    times = hourly["time"]

    max_temperature = max(temperatures)
    max_index = temperatures.index(max_temperature)
    max_time = times[max_index]

    min_temperature = min(temperatures)
    min_index = temperatures.index(min_temperature)
    min_time = times[min_index]

    print()
    print("CURRENT WEATHER")
    print("----------------")
    print("Current temperature:", current["temperature_2m"], "°C")
    print("Feels like:", current["apparent_temperature"], "°C")

    print()
    print("48-HOUR FORECAST ANALYSIS")
    print("-------------------------")
    print("Maximum temperature:", max_temperature, "°C")
    print("Maximum expected at:", max_time)
    print("Minimum temperature:", min_temperature, "°C")
    print("Minimum expected at:", min_time)

    print()
    print("POLYMARKET SEARCH")
    print("-----------------")
    print("Searching for weather markets...")

    data = search_polymarket()

    events = data.get("events", [])
    markets_found = 0

    for event in events:
        for market in event.get("markets", []):
            question = market.get("question")

            if not question:
                continue

            question_lower = question.lower()

            weather_keywords = [
                "weather",
                "temperature",
                "rain",
                "snow",
                "hot",
                "cold",
                "forecast",
            ]

            if not any(keyword in question_lower for keyword in weather_keywords):
                continue

            if market.get("closed") is True:
                continue

            markets_found += 1

            print()
            print("Market:", question)
            print("Active:", market.get("active"))
            print("Volume:", market.get("volume"))

            outcomes = market.get("outcomes")
            prices = market.get("outcomePrices")

            try:
                outcomes = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
                prices = json.loads(prices) if isinstance(prices, str) else prices

                if outcomes and prices:
                    print("Prices:")

                    for outcome, price in zip(outcomes, prices):
                        print("  ", outcome, "=", price)

            except (json.JSONDecodeError, TypeError):
                print("Prices: unavailable")

    print()
    print("Weather markets found:", markets_found)
    print("Hourly forecast loaded:", len(temperatures), "hours")


if __name__ == "__main__":
    main()
