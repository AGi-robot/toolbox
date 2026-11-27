# Grace's lighting catalogue

Colours and effects are editable data. The presets are examples, not a fixed list of occasions or keyword triggers. Grace may choose any fitting effect from the current conversation, mood, history, or timing.
The seed presets include seasonal, celebratory, atmospheric, focus, and signal effects; Grace can choose or customize any of them.
The `default` preset restores the existing resting-mint and online-rose activity renderer.
Selecting `default` releases expressive control; Console resumes its current automatic activity lighting when running.
Saved effects may carry `reason` and `meaning` strings for explanations and personal codes.
The single JSON block is read whenever a lighting request arrives. Brightness is 0–1.
`rhythm_pattern` contains successive brightness multipliers, equally spaced over `rhythm_seconds`.
Optional `speech_mode` selects `auto` (follow future playback except Morse), `follow`, `keep`, or `blend`; speech modulation never rewrites the saved palette.

```json
{
  "colors": {
    "mint": "#58C77E", "rose": "#B84669", "red": "#FF0000",
    "white": "#FFFFFF", "green": "#00FF00", "gold": "#FFD700",
    "pumpkin": "#FF7518", "purple": "#800080", "sakura": "#FFB7C5",
    "cyan": "#00E5FF", "magenta": "#FF00C8", "violet": "#8A5CFF",
    "aurora_green": "#32FF8A", "teal": "#00BFA5", "deep_blue": "#142850",
    "amber": "#FFB347", "cool_white": "#B8D8FF"
  },
  "effects": {
    "default": {},
    "disco": {"rainbow": true, "transition_seconds": 2, "intermediate_steps": 24, "rhythm": "heartbeat", "rhythm_seconds": 2, "brightness": 0.55, "loop": true, "duration_seconds": null},
    "rainbow": {"rainbow": true, "transition_speed": "slow", "brightness": 0.4, "duration_seconds": 120},
    "red_white_green": {"start_color": "red", "transition_colors": ["white"], "end_color": "green", "transition_speed": "slow"},
    "pumpkin_green": {"start_color": "pumpkin", "end_color": "green", "transition_speed": "slow"},
    "cyberpunk": {"start_color": "magenta", "transition_colors": ["violet"], "end_color": "cyan", "transition_seconds": 4, "brightness": 0.45},
    "aurora": {"start_color": "aurora_green", "transition_colors": ["teal"], "end_color": "violet", "transition_seconds": 12, "brightness": 0.35},
    "ocean": {"start_color": "deep_blue", "transition_colors": ["teal"], "end_color": "cyan", "transition_seconds": 14, "brightness": 0.35},
    "sunset": {"start_color": "pumpkin", "transition_colors": ["rose"], "end_color": "purple", "transition_seconds": 10, "brightness": 0.45},
    "focus": {"start_color": "cool_white", "rhythm": "stationary", "brightness": 0.28},
    "cozy_amber": {"start_color": "amber", "rhythm": "stationary", "brightness": 0.2},
    "red_gold": {"start_color": "red", "end_color": "gold"},
    "sakura_glow": {"start_color": "sakura", "rhythm": "stationary", "brightness": 0.3},
    "dim": {"start_color": "gold", "rhythm": "stationary", "brightness": 0.05},
    "attention": {"start_color": "white", "rhythm": "blink_slow", "brightness": 0.6, "duration_seconds": 12},
    "siren": {"start_color": "red", "end_color": "white", "transition_seconds": 2, "intermediate_steps": 0, "duration_seconds": 12},
    "double_pulse": {"start_color": "rose", "rhythm": "pattern", "rhythm_seconds": 4, "rhythm_pattern": [0, 1, 0.2, 0.7, 0.1, 0, 0, 0]},
    "morse_hello": {"start_color": "mint", "rhythm": "morse", "morse_text": "HELLO", "duration_seconds": 30}
  }
}
```
