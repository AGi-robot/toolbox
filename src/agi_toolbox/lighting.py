"""OpenRGB effect client. Console owns device access and effect validation."""
import httpx

COLOUR = {"type": "string", "pattern": "^(#[0-9a-fA-F]{6}|[A-Za-z0-9_-]{1,64})$"}
LIGHTING_PARAMETERS = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "preset": {"type": "string", "description": "Optional saved effect name from lighting_catalog; other fields override it."},
        "start_color": COLOUR, "end_color": COLOUR,
        "transition_colors": {"type": "array", "items": COLOUR, "maxItems": 16},
        "transition_speed": {"type": "string", "enum": ["fast", "normal", "slow"]},
        "transition_seconds": {"type": "number", "minimum": 1, "maximum": 120},
        "intermediate_steps": {"type": "integer", "minimum": 0, "maximum": 256,
                               "description": "Interpolated steps between colour stops: zero jumps, more is smoother."},
        "brightness": {"type": "number", "minimum": 0, "maximum": 1},
        "rhythm": {"type": "string", "enum": ["steady", "stationary", "blink", "blink_fast", "blink_slow", "heartbeat", "random", "morse", "pattern"]},
        "rhythm_pattern": {"type": "array", "minItems": 1, "maxItems": 64, "items": {"type": "number", "minimum": 0, "maximum": 1}},
        "rhythm_seconds": {"type": "number", "minimum": 1, "maximum": 60},
        "rainbow": {"type": "boolean"}, "loop": {"type": "boolean"},
        "duration_seconds": {"type": "number", "minimum": 0.1, "maximum": 3600},
        "morse_text": {"type": "string", "maxLength": 120, "pattern": "^[A-Za-z0-9 ]*$"},
        "morse_unit_seconds": {"type": "number", "minimum": 0.25, "maximum": 2},
    },
}
LIGHTING_DESCRIPTION = (
    "Compose an expressive lighting effect using colours, gradients, rainbow and rhythms. "
    "Choose whether and how to use it from the conversation; there are no prescribed moods or occasions. "
    "Colours use #RRGGBB or a name in lighting_catalog; brightness is 0–1. transition_seconds overrides transition_speed "
    "(fast=2, normal=5, slow=10 seconds per palette traversal). "
    "steady keeps brightness constant while colours transition; stationary holds start_color. "
    "blink_fast is a 1-second cycle, blink_slow 4 seconds; other rhythms use rhythm_seconds. "
    "rainbow uses the hue wheel instead of the palette; loop repeats transitions. "
    "Morse needs ASCII morse_text; its timing uses morse_unit_seconds. "
    "pattern plays rhythm_pattern brightness multipliers at equal intervals over rhythm_seconds; "
    "each step must last at least 0.25 seconds. Use lighting_catalog to discover saved effects. "
    "Effects replace the previous effect and expire after duration_seconds (default 60). "
    "The result reports device connection status, not a guarantee of visible output."
)


class LightingClient:
    def __init__(self, console_url: str = 'http://127.0.0.1:8853') -> None:
        if not console_url.startswith(('http://', 'https://')):
            raise ValueError('console_url must use HTTP(S)')
        self.url = console_url.rstrip('/') + '/api/lighting'

    def set_effect(self, **effect) -> dict:
        response = httpx.put(self.url, json=effect, timeout=5)
        response.raise_for_status()
        return response.json()

    def status(self) -> dict:
        response = httpx.get(self.url, timeout=5)
        response.raise_for_status()
        return response.json()

    def stop(self) -> dict:
        response = httpx.delete(self.url, timeout=5)
        response.raise_for_status()
        return response.json()


    def catalog(self) -> dict:
        response = httpx.get(self.url + '/catalog', timeout=5)
        response.raise_for_status()
        return response.json()

    def save_preset(self, name: str, effect: dict, colors: dict | None = None) -> dict:
        response = httpx.put(self.url + '/catalog', json={"name": name, "effect": effect, "colors": colors}, timeout=5)
        response.raise_for_status()
        return response.json()


SAVE_LIGHTING_PARAMETERS = {
    "type": "object", "additionalProperties": False, "required": ["name", "effect"],
    "properties": {
        "name": {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,64}$"},
        "effect": {**LIGHTING_PARAMETERS, "properties": {k: v for k, v in LIGHTING_PARAMETERS["properties"].items() if k != "preset"}},
        "colors": {"type": "object", "maxProperties": 128,
                   "propertyNames": {"pattern": "^[A-Za-z0-9_-]{1,64}$"},
                   "additionalProperties": {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"}},
    },
}
