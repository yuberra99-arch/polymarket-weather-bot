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


def main():
    print("Polymarket Weather Bot V1")
    print("Getting weather data...")

    weather = get_weather()

    current = weather["current"]

    print()
    print("Current temperature:", current["temperature_2m"], "°C")
    print("Feels like:", current["apparent_temperature"], "°C")

    print()
    print("Hourly forecast loaded:", len(weather["hourly"]["time"]), "hours")


if __name__ == "__main__":
    main()
