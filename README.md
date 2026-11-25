# Toolbox

Shared, transport-independent utilities for Grace. The first tool returns the current time in an IANA time zone.

```bash
pip install -e .
python -c 'from agi_toolbox import current_time; print(current_time("America/Vancouver"))'
```

Agentic may register this function as a tool. Specialized tools belong in their capability repositories.

`agi_toolbox.weather.current_weather(latitude, longitude)` retrieves current weather from Open-Meteo. Coordinates are sent to the provider; the response includes measurement units and a weather code. No location is guessed from a place name.
