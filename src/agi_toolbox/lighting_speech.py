"""Playback-volume envelope only: no audio, model calls, palettes or hardware reads."""
from collections import deque
import math
import re

from .lighting_effects import _number


class SpeechEnvelope:
    timeout_seconds = 1.0

    def __init__(self):
        self.stream_id = None
        self.sequence = -1
        self.level = 0.0
        self.target = 0.0
        self._seen = 0.0
        self._smoothed_at = 0.0
        self._retired = deque(maxlen=32)

    def reset(self):
        if self.stream_id is not None:
            self._retired.append(self.stream_id)
        self.stream_id = None
        self.sequence = -1
        self.level = self.target = 0.0

    def active(self, now):
        if self.stream_id is not None and now - self._seen >= self.timeout_seconds:
            self.reset()
        return self.stream_id is not None

    def value(self, now):
        if not self.active(now):
            return 0.0
        elapsed = max(0, now - self._smoothed_at)
        tau = 0.04 if self.target > self.level else 0.15
        self.level += (self.target - self.level) * (1 - math.exp(-elapsed / tau))
        self._smoothed_at = now
        return self.level

    def update(self, *, stream_id, event, sequence, level=0.0, now):
        if not isinstance(stream_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', stream_id):
            raise ValueError('stream_id must be 1–64 letters, digits, underscores or hyphens')
        if event not in ('start', 'level', 'stop'):
            raise ValueError('event must be start, level or stop')
        if type(sequence) is not int or not 0 <= sequence <= 2**53 - 1:
            raise ValueError('sequence must be a non-negative safe integer')
        _number('level', level, 0, 1)
        if event == 'start' and sequence != 0:
            raise ValueError('A start event must use sequence 0')
        self.value(now)
        if event == 'start':
            if stream_id == self.stream_id or stream_id in self._retired:
                return False
            self.reset()
            self.stream_id = stream_id
            self._smoothed_at = now
        elif self.stream_id != stream_id or sequence <= self.sequence:
            return False
        self.sequence = sequence
        self._seen = now
        self.target = level
        if event == 'stop':
            self.reset()
        return True
