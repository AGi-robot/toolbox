# Toolbox

Shared, transport-independent utilities for Grace. The first tool returns the current time in an IANA time zone.

```bash
pip install -e .
python -c 'from agi_toolbox import current_time; print(current_time("America/Vancouver"))'
```

Agentic may register this function as a tool. Specialized tools belong in their capability repositories.

`agi_toolbox.weather.current_weather(latitude, longitude)` retrieves current weather from Open-Meteo. Coordinates are sent to the provider; the response includes measurement units and a weather code. No location is guessed from a place name.

## Expressive lighting

Toolbox implements Grace's expressive lighting capability. Agentic and Interactive decide when to use it through the exported tool contracts; Console provides automatic activity lighting independently.

Install the service extra and start it on the OpenRGB host:

```bash
pip install -e '.[lighting]'
grace-lighting
```

An OpenRGB SDK server must be running on `127.0.0.1:6742` (start OpenRGB with `--server`; Console can also start it). The capability does not require Console to run. The API listens on loopback port 8854 and owns its renderer and persistent Markdown catalogue. See [LIGHTING.md](LIGHTING.md) for configuration, device coordination, fields, and limitations.

```python
from agi_toolbox.lighting import LightingClient
lights = LightingClient('http://127.0.0.1:8854')
lights.set_effect(preset='cyberpunk', reason='A colourful glow for our coding session')
lights.set_effect(preset='default', reason='Return to normal activity lighting')
```

`catalog()` discovers presets; `save_preset(name, effect, reason, colors=None, meaning='')` validates and saves without playing. All model-facing changes require a reason, and personal signals can carry a meaning. Existing `~/.agi/lighting.md` files remain usable. Console no longer hosts `/api/lighting`; change client URLs from port 8853 to the independent service and use `AGI_LIGHTING_SERVICE_URL` in Interactive.
