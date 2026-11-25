"""Current weather from Open-Meteo by explicit coordinates."""
import math
import httpx


def current_weather(latitude: float, longitude: float) -> dict:
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in (latitude, longitude)):
        raise ValueError("coordinates must be finite numbers")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("invalid latitude or longitude")
    response = httpx.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": latitude, "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
        "timezone": "auto"}, timeout=15)
    response.raise_for_status()
    data = response.json()
    return {"latitude": data["latitude"], "longitude": data["longitude"], "timezone": data["timezone"],
            "current": data["current"], "units": data["current_units"], "source": "https://open-meteo.com/"}
