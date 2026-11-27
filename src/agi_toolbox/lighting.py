"""Client and model tool contracts for the independent expressive lighting service."""
import httpx

COLOUR = {"type": "string", "pattern": "^(#[0-9a-fA-F]{6}|[A-Za-z0-9_-]{1,64})$"}
LIGHTING_PARAMETERS = {
    "type": "object", "additionalProperties": False, "required": ["reason"],
    "properties": {
        "reason": {"type": "string", "minLength": 1, "maxLength": 1000, "description": "Brief explanation of this choice for regular memory; not private reasoning."},
        "meaning": {"type": "string", "maxLength": 1000, "description": "Optional meaning of a personal colour or blinking code that can be taught to the user."},
        "preset": {"type": "string", "description": "Optional saved effect name from lighting_catalog; other fields override it."},
        "start_color": COLOUR, "end_color": COLOUR,
        "transition_colors": {"type": "array", "items": COLOUR, "maxItems": 16},
        "transition_speed": {"type": "string", "enum": ["fast", "normal", "slow"]},
        "transition_seconds": {"type": "number", "minimum": 1, "maximum": 120},
        "intermediate_steps": {"type": "integer", "minimum": 0, "maximum": 256,
                               "description": "Interpolated steps between colour stops: zero jumps, more is smoother."},
        "brightness": {"type": "number", "minimum": 0, "maximum": 1},
        "rhythm": {"type": "string", "enum": ["steady", "stationary", "blink", "blink_fast", "blink_slow", "heartbeat", "random", "morse", "pattern"]},
        "speech_mode": {"type": "string", "enum": ["auto", "follow", "keep", "blend"],
                        "description": "During future TTS playback: auto follows voice except for Morse; follow replaces brightness rhythm, keep preserves it, blend gently modulates it. Palette stays unchanged."},
        "rhythm_pattern": {"type": "array", "minItems": 1, "maxItems": 64, "items": {"type": "number", "minimum": 0, "maximum": 1}},
        "rhythm_seconds": {"type": "number", "minimum": 1, "maximum": 60},
        "rainbow": {"type": "boolean"}, "loop": {"type": "boolean"},
        "duration_seconds": {"type": ["number", "null"], "minimum": 0.1, "maximum": 3600},
        "morse_text": {"type": "string", "maxLength": 120, "pattern": "^[A-Za-z0-9 ]*$"},
        "morse_unit_seconds": {"type": "number", "minimum": 0.25, "maximum": 2},
    },
}
LIGHTING_DESCRIPTION = (
    "Compose an expressive lighting effect using colours, gradients, rainbow and rhythms. "
    "Choose whether and which lighting effect to use from the current conversation, mood, history or timing. "
    "Discover presets through lighting_catalog; their names and examples are suggestions, not fixed keyword triggers. "
    "Decide freely when any effect fits, including out of the blue during an active chat. "
    "Colours use #RRGGBB or a name in lighting_catalog; brightness is 0–1. transition_seconds overrides transition_speed "
    "(fast=2, normal=5, slow=10 seconds per palette traversal). "
    "steady keeps brightness constant while colours transition; stationary holds start_color. "
    "blink_fast is a 1-second cycle, blink_slow 4 seconds; other rhythms use rhythm_seconds. "
    "speech_mode selects auto, follow, keep or blend for future voice brightness; auto preserves Morse and otherwise follows speech. "
    "rainbow uses the hue wheel instead of the palette; loop repeats transitions. "
    "When asked to return to normal or restore the lights, use preset=default to release expressive control and resume automatic activity lighting. "
    "When asked for a different look, choose an effect that fits the current context; it replaces the current one. "
    "Supply a brief reason for every change. "
    "Personal colour/blink codes may include meaning so you can explain them later. "
    "Morse accepts up to 120 characters per effect; longer messages can be split. "
    "Morse needs ASCII morse_text; its timing uses morse_unit_seconds. "
    "pattern plays rhythm_pattern brightness multipliers at equal intervals over rhythm_seconds; "
    "each step must last at least 0.25 seconds. Use lighting_catalog to discover saved effects. "
    "Effects replace the previous effect. duration_seconds is optional; omit or use null to keep it "
    "until replaced or stopped, or choose a bounded duration. "
    "The result reports device connection status, not a guarantee of visible output."
)


class LightingClient:
    def __init__(self, service_url: str = 'http://127.0.0.1:8854') -> None:
        if not service_url.startswith(('http://', 'https://')):
            raise ValueError('service_url must use HTTP(S)')
        self.url = service_url.rstrip('/') + '/api/lighting'

    def set_effect(self, **effect) -> dict:
        _reason(effect.get("reason"))
        response = httpx.put(self.url, json=effect, timeout=5)
        response.raise_for_status()
        return response.json()

    def status(self) -> dict:
        response = httpx.get(self.url, timeout=5)
        response.raise_for_status()
        return response.json()

    def stop(self, reason: str) -> dict:
        _reason(reason)
        response = httpx.delete(self.url, timeout=5)
        response.raise_for_status()
        return response.json()


    def speech_event(self, *, stream_id: str, event: str, sequence: int, level: float = 0) -> dict:
        """Future audio player calls this at playback time; it is not a model tool."""
        response = httpx.put(self.url + '/speech', json={
            'stream_id': stream_id, 'event': event, 'sequence': sequence, 'level': level,
        }, timeout=5)
        response.raise_for_status()
        return response.json()

    def catalog(self) -> dict:
        response = httpx.get(self.url + '/catalog', timeout=5)
        response.raise_for_status()
        return response.json()

    def save_preset(self, name: str, effect: dict, reason: str, colors: dict | None = None, meaning: str = '') -> dict:
        _reason(reason)
        response = httpx.put(self.url + '/catalog', json={"name": name, "effect": effect, "colors": colors, "reason": reason, "meaning": meaning}, timeout=5)
        response.raise_for_status()
        return response.json()


SAVE_LIGHTING_PARAMETERS = {
    "type": "object", "additionalProperties": False, "required": ["name", "effect", "reason"],
    "properties": {
        "reason": LIGHTING_PARAMETERS["properties"]["reason"],
        "meaning": LIGHTING_PARAMETERS["properties"]["meaning"],
        "name": {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,64}$"},
        "effect": {**LIGHTING_PARAMETERS, "required": [], "properties": {k: v for k, v in LIGHTING_PARAMETERS["properties"].items() if k != "preset"}},
        "colors": {"type": "object", "maxProperties": 128,
                   "propertyNames": {"pattern": "^[A-Za-z0-9_-]{1,64}$"},
                   "additionalProperties": {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"}},
    },
}


STOP_LIGHTING_PARAMETERS = {"type": "object", "additionalProperties": False,
                            "required": ["reason"], "properties": {
                                "reason": LIGHTING_PARAMETERS["properties"]["reason"]}}


def _reason(reason):
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValueError('Supply a brief reason (1–1000 characters) for lighting changes')
