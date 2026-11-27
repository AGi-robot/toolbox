"""Playback timing, scene composition and ownership, without audio or RGB hardware."""
from unittest.mock import Mock
import fcntl
import math

from fastapi.testclient import TestClient
import pytest

from agi_toolbox.lighting_device import LightingDevice
from agi_toolbox.lighting_effects import LightingEffect
from agi_toolbox.lighting_server import create_app
from agi_toolbox.lighting_speech import SpeechEnvelope


@pytest.fixture
def renderer(tmp_path, monkeypatch):
    clock = [10.0]
    monkeypatch.setenv('AGI_OPENRGB_LOCK_PATH', str(tmp_path / 'rgb.lock'))
    monkeypatch.setenv('AGI_LIGHTING_CATALOG', str(tmp_path / 'lighting.md'))
    rgb = LightingDevice(clock=lambda: clock[0])
    rgb._thread = Mock(is_alive=lambda: True)
    rgb._write = Mock()
    yield rgb, clock
    rgb.clear_effect()


def test_follow_voice_preserves_colour_and_restores_original_rhythm(renderer):
    rgb, clock = renderer
    effect = LightingEffect(start_color='#336699', brightness=.6, rhythm='blink_fast')
    rgb.set_effect(effect)
    clock[0] = 10.75  # the underlying blink is currently off
    rgb.speech_event(stream_id='a', event='start', sequence=0, level=1)
    clock[0] = 10.85
    rgb._tick()
    colour = rgb._write.call_args.args[0]
    assert colour[2] > colour[1] > colour[0] > 0
    assert max(colour) <= 153 * .6
    assert rgb.status()['effect']['rhythm'] == 'blink_fast'
    rgb.speech_event(stream_id='a', event='stop', sequence=1)
    assert rgb._write.call_args.args[0] == effect.color_at(.85) == (0, 0, 0)
    assert rgb._effect is effect


@pytest.mark.parametrize('mode', ['keep', 'blend'])
def test_speech_policy_preserves_intentional_rhythm(renderer, mode):
    rgb, clock = renderer
    effect = LightingEffect(start_color='#FF6600', rhythm='blink_fast', speech_mode=mode)
    rgb.set_effect(effect)
    rgb.speech_event(stream_id='a', event='start', sequence=0, level=1)
    clock[0] = 10.7  # blink remains off, including during speech
    rgb._tick()
    assert rgb._write.call_args.args[0] == (0, 0, 0)
    clock[0] = 11.1
    rgb._tick()
    normal = effect.color_at(1.1)
    result = rgb._write.call_args.args[0]
    if mode == 'keep':
        assert result == normal
    else:
        assert all(round(.65 * channel) <= actual <= channel for actual, channel in zip(result, normal))


def test_auto_keeps_morse_timing(renderer):
    rgb, clock = renderer
    effect = LightingEffect(rhythm='morse', morse_text='E')
    rgb.set_effect(effect)
    rgb.speech_event(stream_id='a', event='start', sequence=0, level=1)
    clock[0] = 10.3  # the Morse dot has finished
    rgb._tick()
    assert rgb.status()['speech']['policy'] == 'keep'
    assert rgb._write.call_args.args[0] == (0, 0, 0)


def test_speech_without_custom_scene_releases_device_after_timeout(renderer):
    rgb, clock = renderer
    rgb.speech_event(stream_id='a', event='start', sequence=0, level=.8)
    assert rgb.status()['active']
    assert rgb.status()['effect'] is None
    assert rgb._lease is not None
    clock[0] += 1.01
    rgb._tick()
    assert not rgb.status()['active']
    assert rgb._lease is None
    assert not rgb.speech_event(stream_id='a', event='level', sequence=1, level=1)['accepted']


def test_default_cancels_overlay_and_late_packets_cannot_restart_it(renderer):
    rgb, _ = renderer
    rgb.set_effect(LightingEffect())
    rgb.speech_event(stream_id='a', event='start', sequence=0, level=.5)
    rgb.clear_effect()
    for event, seq in [('level', 1), ('start', 0), ('stop', 2)]:
        assert not rgb.speech_event(stream_id='a', event=event, sequence=seq)['accepted']
    assert rgb._lease is None
    rgb.speech_event(stream_id='b', event='start', sequence=0, level=.5)
    assert rgb.status()['speech']['active']
    rgb.speech_event(stream_id='b', event='stop', sequence=1)
    assert rgb._lease is None


def test_scene_expiry_during_playback_uses_configured_fallback(renderer):
    rgb, clock = renderer
    rgb.set_effect(LightingEffect(start_color='#0000FF', duration_seconds=.1))
    rgb.speech_event(stream_id='a', event='start', sequence=0, level=1)
    clock[0] += .2
    rgb._tick()
    assert rgb.status()['effect'] is None
    assert rgb.status()['speech']['active']
    assert rgb._lease is not None
    # Fallback is the catalogue's rose double_pulse palette, with voice rhythm.
    red, green, blue = rgb._write.call_args.args[0]
    assert red > blue > green


def test_envelope_rejects_invalid_and_reordered_events_and_smooths():
    env = SpeechEnvelope()
    assert env.update(stream_id='a', event='start', sequence=0, level=1, now=1)
    assert 0 < env.value(1.04) < 1
    assert env.update(stream_id='a', event='level', sequence=2, level=0, now=1.05)
    assert not env.update(stream_id='a', event='level', sequence=1, level=1, now=1.06)
    assert not env.update(stream_id='other', event='stop', sequence=3, now=1.06)
    previous = env.value(1.06)
    assert 0 < env.value(1.1) < previous
    for level in [-1, 2, math.nan, math.inf, True]:
        with pytest.raises(ValueError):
            env.update(stream_id='a', event='level', sequence=3, level=level, now=1.1)


def test_speech_api_validates_and_reports_rendering_errors(renderer):
    rgb, _ = renderer
    client = TestClient(create_app(rgb))
    endpoint = '/api/lighting/speech'
    assert client.put(endpoint, json={'stream_id': 'a', 'event': 'start', 'sequence': 0, 'level': .5}).json()['accepted']
    assert client.put(endpoint, json={'stream_id': 'a', 'event': 'level', 'sequence': 1, 'level': .8}).status_code == 200
    for data in [[], {}, {'stream_id': 'a', 'event': 'invalid', 'sequence': 2},
                 {'stream_id': 'a', 'event': 'level', 'sequence': True},
                 {'stream_id': 'b', 'event': 'start', 'sequence': 1},
                 {'stream_id': 'a', 'event': 'level', 'sequence': 2, 'level': 2}]:
        assert client.put(endpoint, json=data).status_code == 422
    rgb._write.side_effect = OSError('SDK disconnected')
    assert client.put(endpoint, json={'stream_id': 'a', 'event': 'level', 'sequence': 2, 'level': 0}).status_code == 503
    assert rgb._lease is None
    assert not rgb.status()['active']


def test_busy_device_cannot_claim_speech_started(renderer, tmp_path):
    rgb, _ = renderer
    with (tmp_path / 'rgb.lock').open('a') as other:
        fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match='busy'):
            rgb.speech_event(stream_id='a', event='start', sequence=0, level=1)
    assert not rgb.status()['speech']['active']
    assert rgb._lease is None
