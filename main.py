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
    print("Hourly forecast loaded:", len(temperatures), "hours")


if __name__ == "__main__":
    main()
