"""Pure, bounded lighting effects; no device I/O or situation-to-colour rules."""
from __future__ import annotations

import colorsys
import math
import random
import re
from dataclasses import dataclass, field

MORSE = dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', (
    '.-', '-...', '-.-.', '-..', '.', '..-.', '--.', '....', '..', '.---', '-.-',
    '.-..', '--', '-.', '---', '.--.', '--.-', '.-.', '...', '-', '..-', '...-',
    '.--', '-..-', '-.--', '--..', '-----', '.----', '..---', '...--', '....-',
    '.....', '-....', '--...', '---..', '----.')))
SPEEDS = {'fast': 2.0, 'normal': 5.0, 'slow': 10.0}
RHYTHMS = {'steady', 'stationary', 'blink', 'blink_fast', 'blink_slow',
           'heartbeat', 'random', 'morse', 'pattern'}


def _colour(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        raise ValueError('Colours must use #RRGGBB')
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def _number(name: str, value: float, low: float, high: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be a finite number from {low} to {high}')


def morse_units(text: str) -> tuple[int, ...]:
    """ITU timing: one-unit dot/gap, three-unit dash/letter gap, seven-unit word gap."""
    units = []
    for word_index, word in enumerate(text.upper().split()):
        if word_index:
            units.extend([0] * 7)
        for letter_index, letter in enumerate(word):
            if letter_index:
                units.extend([0] * 3)
            for symbol_index, symbol in enumerate(MORSE[letter]):
                if symbol_index:
                    units.append(0)
                units.extend([1] * (1 if symbol == '.' else 3))
    # Delimit repeated messages, including single letters.
    return tuple(units + [0] * 7)


@dataclass(frozen=True)
class LightingEffect:
    reason: str = ''
    meaning: str = ''
    start_color: str = '#58C77E'
    end_color: str | None = None
    transition_colors: list[str] = field(default_factory=list)
    transition_speed: str = 'normal'
    transition_seconds: float | None = None
    intermediate_steps: int = 64
    brightness: float = 0.5
    rhythm: str = 'steady'
    rhythm_seconds: float = 2.0
    rhythm_pattern: list[float] = field(default_factory=list)
    rainbow: bool = False
    loop: bool = True
    duration_seconds: float | None = None
    morse_text: str = ''
    morse_unit_seconds: float = 0.25
    _palette: tuple = field(init=False, repr=False)
    _morse: tuple = field(init=False, repr=False)

    def __post_init__(self) -> None:
        for key in ('reason', 'meaning'):
            if not isinstance(getattr(self, key), str) or len(getattr(self, key)) > 1000:
                raise ValueError(f'{key} must be a string of at most 1000 characters')
        if not isinstance(self.transition_colors, list) or len(self.transition_colors) > 16:
            raise ValueError('transition_colors must be a list of at most 16 hex colours')
        palette = [_colour(self.start_color)] + [_colour(c) for c in self.transition_colors]
        if self.end_color is not None:
            palette.append(_colour(self.end_color))
        if self.transition_speed not in SPEEDS or self.rhythm not in RHYTHMS:
            raise ValueError('Unknown transition_speed or rhythm')
        if type(self.intermediate_steps) is not int or not 0 <= self.intermediate_steps <= 256:
            raise ValueError('intermediate_steps must be an integer from 0 to 256')
        if type(self.loop) is not bool or type(self.rainbow) is not bool:
            raise ValueError('loop and rainbow must be booleans')
        _number('brightness', self.brightness, 0, 1)
        if self.duration_seconds is not None:
            _number('duration_seconds', self.duration_seconds, 0.1, 3600)
        _number('rhythm_seconds', self.rhythm_seconds, 1, 60)
        _number('morse_unit_seconds', self.morse_unit_seconds, 0.25, 2)
        if not isinstance(self.rhythm_pattern, list) or len(self.rhythm_pattern) > 64:
            raise ValueError('rhythm_pattern must contain at most 64 brightness multipliers')
        for level in self.rhythm_pattern:
            _number('rhythm_pattern level', level, 0, 1)
        if self.rhythm == 'pattern' and not self.rhythm_pattern:
            raise ValueError('pattern rhythm needs rhythm_pattern')
        if self.rhythm_pattern and self.rhythm_seconds / len(self.rhythm_pattern) < 0.25:
            raise ValueError('Each rhythm_pattern step must last at least 0.25 seconds')
        if self.transition_seconds is not None:
            _number('transition_seconds', self.transition_seconds, 1, 120)
        if not isinstance(self.morse_text, str) or len(self.morse_text) > 120 or any(c not in MORSE and c != ' ' for c in self.morse_text.upper()):
            raise ValueError('morse_text accepts at most 120 ASCII letters, digits and spaces')
        if self.rhythm == 'morse' and not self.morse_text.strip():
            raise ValueError('morse_text is required for Morse rhythm')
        object.__setattr__(self, '_palette', tuple(palette))
        object.__setattr__(self, '_morse', morse_units(self.morse_text) if self.rhythm == 'morse' else ())

    def color_at(self, elapsed: float) -> tuple[int, int, int]:
        period = self.transition_seconds or SPEEDS[self.transition_speed]
        position = max(0, elapsed) / period
        # Palette loops ping-pong for continuity; rainbow loops around the hue wheel.
        if self.loop:
            phase = position % 1 if self.rainbow else 1 - abs(position % 2 - 1)
        else:
            phase = min(position, 1)
        if self.intermediate_steps == 0:
            steps = max(1, len(self._palette) - 1) if not self.rainbow else 6
            phase = (math.floor(phase * steps) if self.rainbow else math.floor(phase * steps + 0.5)) / steps
        elif self.rainbow:
            steps = self.intermediate_steps + 1
            phase = round(phase * steps) / steps
        if self.rhythm == "stationary":
            phase = 0.0
        if self.rainbow and self.rhythm != "stationary":
            source = tuple(c * 255 for c in colorsys.hsv_to_rgb(phase, 1, 1))
        else:
            index = phase * (len(self._palette) - 1)
            left = min(int(index), len(self._palette) - 1)
            right = min(left + 1, len(self._palette) - 1)
            fraction = index - left
            if self.intermediate_steps:
                steps = self.intermediate_steps + 1
                fraction = round(fraction * steps) / steps
            source = tuple(a + (b - a) * fraction for a, b in zip(self._palette[left], self._palette[right]))
        amount = 1.0
        cycle = {'blink_fast': 1.0, 'blink_slow': 4.0}.get(self.rhythm, self.rhythm_seconds)
        phase = (elapsed % cycle) / cycle
        if self.rhythm.startswith('blink'):
            amount = float(phase < 0.5)
        elif self.rhythm == 'heartbeat':
            amount = max(math.exp(-((phase - 0.15) / 0.07) ** 2),
                         0.7 * math.exp(-((phase - 0.40) / 0.09) ** 2))
        elif self.rhythm == 'random':
            amount = random.Random(int(elapsed / cycle)).uniform(0.1, 1)
        elif self.rhythm == 'pattern':
            amount = self.rhythm_pattern[min(int(phase * len(self.rhythm_pattern)), len(self.rhythm_pattern) - 1)]
        elif self.rhythm == 'morse':
            amount = self._morse[int(elapsed / self.morse_unit_seconds) % len(self._morse)]
        return tuple(round(c * self.brightness * amount) for c in source)
