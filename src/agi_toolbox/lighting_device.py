"""Expressive OpenRGB renderer; a Linux file lock coordinates with activity lighting."""
from __future__ import annotations

from dataclasses import asdict
import fcntl
import logging
import math
import os
from pathlib import Path
import threading
import time

from .lighting_effects import LightingEffect
from .lighting_speech import SpeechEnvelope
from .lighting_catalog import resolve_effect

LOG = logging.getLogger(__name__)


class LightingDevice:
    def __init__(self, *, clock=None):
        self._clock = clock or time.monotonic
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._lease = None
        self._client = None
        self._device = None
        self._effect = None
        self._started = 0.0
        self._last_color = None
        self._error = None
        self._speech = SpeechEnvelope()
        self._speech_base = None
        self._speech_started = 0.0
        # Reuse the bounded session/sequence tracker; response activity has no
        # audio level and renews less frequently than playback samples.
        self._response = SpeechEnvelope()
        self._response.timeout_seconds = 3.0
        self._response_base = None
        self._response_started = 0.0

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._animate, name='aiva-expressive-lighting', daemon=True)
            self._thread.start()

    def _claim(self):
        if self._lease is not None:
            return
        path = Path(os.getenv('AGI_OPENRGB_LOCK_PATH', '~/.agi/openrgb-device.lock')).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        lease = path.open('a')
        deadline = time.monotonic() + 0.25
        while True:
            try:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() < deadline:
                    time.sleep(0.01)  # allow a brief activity frame to finish
                    continue
                lease.close()
                raise RuntimeError('OpenRGB device is busy; another renderer holds its lock') from None
            except OSError:
                lease.close()
                raise
        self._lease = lease

    def _disconnect(self):
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:
                pass
        self._client = self._device = None
        self._last_color = None

    def _write(self, color):
        if self._client is None:
            from openrgb import OpenRGBClient
            self._client = OpenRGBClient(address=os.getenv('AGI_OPENRGB_HOST', '127.0.0.1'),
                                         port=int(os.getenv('AGI_OPENRGB_PORT', '6742')),
                                         name='AIVA expressive lighting', protocol_version=4)
            devices = self._client.get_devices_by_name(
                os.getenv('AGI_OPENRGB_DEVICE', 'MSI Z790 GAMING PLUS WIFI'), exact=False)
            if not devices:
                raise RuntimeError('Configured OpenRGB device was not found')
            self._device = devices[0]
            self._device.set_mode('Static')
        if color != self._last_color:
            from openrgb.utils import RGBColor
            self._device.set_color(RGBColor(*color))
            self._last_color = color

    def set_effect(self, effect: LightingEffect):
        with self._lock:
            if os.getenv('AGI_OPENRGB_ENABLED', 'true').strip().lower() not in {'1', 'true', 'yes', 'on'}:
                raise RuntimeError('OpenRGB is disabled')
            if self._thread is None or not self._thread.is_alive():
                raise RuntimeError('Lighting renderer is not running')
            previous = self._effect
            self._claim()
            try:
                self._write(self._render_color(effect, 0, self._clock()))
            except Exception as error:
                self._error = str(error)
                self._disconnect()
                if previous is None:
                    self.clear_effect()
                raise RuntimeError(f'Could not apply OpenRGB effect: {error}') from error
            self._effect = effect
            self._started = self._clock()
            self._error = None
            return self.status()

    def _release(self):
        self._disconnect()
        if self._lease is not None:
            self._lease.close()  # close releases flock, including on process exit
            self._lease = None

    def clear_effect(self):
        with self._lock:
            self._effect = None
            self._speech.reset()
            self._response.reset()
            self._release()
            return self.status()

    @staticmethod
    def _speech_policy(effect):
        if effect.speech_mode == 'auto':
            return 'keep' if effect.rhythm == 'morse' else 'follow'
        return effect.speech_mode

    def _render_color(self, effect, elapsed, now):
        level = self._speech.value(now)
        if not self._speech.active(now):
            if not self._response.active(now):
                return effect.color_at(elapsed)
            phase = ((now - self._response_started) % 0.4) / 0.4
            level = max(math.exp(-((phase - 0.15) / 0.07) ** 2),
                        0.7 * math.exp(-((phase - 0.40) / 0.09) ** 2))
        policy = self._speech_policy(effect)
        if policy == 'keep':
            return effect.color_at(elapsed)
        if policy == 'blend':
            return tuple(round(c * (0.65 + 0.35 * level)) for c in effect.color_at(elapsed))
        # Override only brightness modulation; palette, transitions and configured
        # peak brightness still come from the selected effect, never hardware.
        return effect.color_at(elapsed, rhythm_amount=0.08 + 0.92 * level)

    def speech_event(self, *, stream_id, event, sequence, level=0.0):
        with self._lock:
            now = self._clock()
            if self._thread is None or not self._thread.is_alive():
                raise RuntimeError('Lighting renderer is not running')
            if os.getenv('AGI_OPENRGB_ENABLED', 'true').strip().lower() not in {'1', 'true', 'yes', 'on'}:
                raise RuntimeError('OpenRGB is disabled')
            # Resolve once per new playback session, not once per volume sample.
            base = None
            if event == 'start':
                name = os.getenv('AGI_LIGHTING_SPEECH_PRESET', 'double_pulse')
                base = resolve_effect({'preset': name})
                if base is None:
                    raise ValueError('Speech fallback must be a colour preset, not default')
            accepted = self._speech.update(stream_id=stream_id, event=event,
                                           sequence=sequence, level=level, now=now)
            if accepted:
                if event == 'start':
                    self._speech_base = base
                    self._speech_started = now
                try:
                    self._frame(now)
                except Exception as error:
                    self._error = str(error)
                    self.clear_effect()
                    raise RuntimeError(f'Could not apply speech lighting: {error}') from error
            return {'accepted': accepted, **self.status()}

    def response_event(self, *, stream_id, event, sequence):
        with self._lock:
            if event not in ('start', 'keepalive', 'stop'):
                raise ValueError('event must be start, keepalive or stop')
            if self._thread is None or not self._thread.is_alive():
                raise RuntimeError('Lighting renderer is not running')
            if os.getenv('AGI_OPENRGB_ENABLED', 'true').strip().lower() not in {'1', 'true', 'yes', 'on'}:
                raise RuntimeError('OpenRGB is disabled')
            now = self._clock()
            base = None
            if event == 'start':
                base = resolve_effect({'preset': os.getenv('AGI_LIGHTING_RESPONSE_PRESET', 'double_pulse')})
                if base is None:
                    raise ValueError('Response fallback must be a colour preset, not default')
            accepted = self._response.update(stream_id=stream_id,
                event='level' if event == 'keepalive' else event, sequence=sequence, now=now)
            if accepted:
                if event == 'start':
                    self._response_base = base
                    self._response_started = now
                try:
                    self._frame(now)
                except Exception as error:
                    self._error = str(error)
                    self.clear_effect()
                    raise RuntimeError(f'Could not apply response lighting: {error}') from error
            return {'accepted': accepted, **self.status()}

    def status(self):
        with self._lock:
            now = self._clock()
            effect = self._effect
            remaining = (max(0, effect.duration_seconds - (now - self._started))
                         if effect and effect.duration_seconds is not None else None)
            level = self._speech.value(now)
            speaking = self._speech.active(now)
            responding = self._response.active(now)
            base = effect if effect is not None else self._speech_base if speaking else self._response_base
            return {'active': bool((effect and (remaining is None or remaining > 0)) or speaking or responding),
                    'effect': {k: v for k, v in asdict(effect).items() if not k.startswith('_')} if effect else None,
                    'remaining_seconds': remaining, 'connected': self._device is not None,
                    'error': self._error,
                    'response': {'active': responding, 'stream_id': self._response.stream_id},
                    'modulation': 'speech' if speaking else 'response' if responding else 'preset' if effect else 'default',
                    'speech': {'active': speaking, 'stream_id': self._speech.stream_id,
                               'level': level, 'policy': self._speech_policy(base) if speaking and base else None},
                    'morse_message_seconds': len(effect._morse) * effect.morse_unit_seconds if effect and effect.rhythm == 'morse' else None}

    def _frame(self, now):
        if self._effect is not None:
            if self._effect.duration_seconds is not None and now - self._started >= self._effect.duration_seconds:
                self._effect = None
        speaking = self._speech.active(now)
        responding = self._response.active(now)
        if self._effect is None and not speaking and not responding:
            self._release()
            return
        effect = self._effect if self._effect is not None else self._speech_base if speaking else self._response_base
        elapsed = now - (self._started if self._effect is not None else self._speech_started if speaking else self._response_started)
        self._claim()
        self._write(self._render_color(effect, elapsed, now))
        self._error = None

    def _tick(self):
        with self._lock:
            try:
                self._frame(self._clock())
            except Exception as error:
                LOG.warning('Expressive lighting failed: %s', error)
                self._error = str(error)
                self.clear_effect()  # yield to activity lighting on device failure

    def _animate(self):
        while not self._stop.wait(0.033):
            self._tick()

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self.clear_effect()
