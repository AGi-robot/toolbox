"""Expressive OpenRGB renderer; a Linux file lock coordinates with activity lighting."""
from __future__ import annotations

from dataclasses import asdict
import fcntl
import logging
import os
from pathlib import Path
import threading
import time

from .lighting_effects import LightingEffect

LOG = logging.getLogger(__name__)


class LightingDevice:
    def __init__(self):
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

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._animate, name='grace-expressive-lighting', daemon=True)
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
                                         name='Grace expressive lighting', protocol_version=4)
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
                self._write(effect.color_at(0))
            except Exception as error:
                self._error = str(error)
                self._disconnect()
                if previous is None:
                    self.clear_effect()
                raise RuntimeError(f'Could not apply OpenRGB effect: {error}') from error
            self._effect = effect
            self._started = time.monotonic()
            self._error = None
            return self.status()

    def clear_effect(self):
        with self._lock:
            self._effect = None
            self._disconnect()
            if self._lease is not None:
                self._lease.close()  # close releases flock, including on process exit
                self._lease = None
            return self.status()

    def status(self):
        with self._lock:
            effect = self._effect
            remaining = (max(0, effect.duration_seconds - (time.monotonic() - self._started))
                         if effect and effect.duration_seconds is not None else None)
            return {'active': bool(effect and (remaining is None or remaining > 0)),
                    'effect': {k: v for k, v in asdict(effect).items() if not k.startswith('_')} if effect else None,
                    'remaining_seconds': remaining, 'connected': self._device is not None,
                    'error': self._error,
                    'morse_message_seconds': len(effect._morse) * effect.morse_unit_seconds if effect and effect.rhythm == 'morse' else None}

    def _tick(self):
        with self._lock:
            if self._effect is None:
                return
            elapsed = time.monotonic() - self._started
            if self._effect.duration_seconds is not None and elapsed >= self._effect.duration_seconds:
                self.clear_effect()
                return
            try:
                self._write(self._effect.color_at(elapsed))
                self._error = None
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
