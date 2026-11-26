# Toolbox

Shared, transport-independent utilities for Grace. The first tool returns the current time in an IANA time zone.

```bash
pip install -e .
python -c 'from agi_toolbox import current_time; print(current_time("America/Vancouver"))'
```

Agentic may register this function as a tool. Specialized tools belong in their capability repositories.

`agi_toolbox.weather.current_weather(latitude, longitude)` retrieves current weather from Open-Meteo. Coordinates are sent to the provider; the response includes measurement units and a weather code. No location is guessed from a place name.

## Expressive lighting

`agi_toolbox.lighting.LightingClient(console_url)` provides `set_effect(**effect)`, `status()` and `stop()` for Console's `/api/lighting` API. The module exports `LIGHTING_PARAMETERS` and `LIGHTING_DESCRIPTION` for model tool registration. Install the matching Console effect API before enabling this tool.

```python
from agi_toolbox.lighting import LightingClient
lights = LightingClient('http://127.0.0.1:8853')
lights.set_effect(start_color='#FF8844', end_color='#6633FF',
                  transition_speed='slow', intermediate_steps=64,
                  brightness=0.4, rhythm='heartbeat', duration_seconds=60)
```

The model can choose colours and effects freely. There are no occasion or mood rules. See [Console's lighting contract](https://github.com/Project-AGi/console/blob/dev/LIGHTING.md) for all fields, defaults and timing semantics. Hardware access stays in Console; Toolbox does not launch OpenRGB or load Grace's chat implementation.

`LightingClient.catalog()` reads editable named colours and effects. `save_preset(name, effect, colors=None)` adds or replaces them in Console's runtime Markdown catalogue without starting the effect. `set_effect(preset='my_effect')` plays one; other fields override saved values. `SAVE_LIGHTING_PARAMETERS` provides the save tool schema. Custom rhythms can be expressed as `rhythm='pattern'` plus `rhythm_pattern` brightness multipliers, without modifying code.
