"""Exercise the independent API and real file-lock lifecycle without RGB hardware."""
import fcntl
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
import pytest

from agi_toolbox.lighting_device import LightingDevice
from agi_toolbox.lighting_effects import LightingEffect
from agi_toolbox.lighting_server import create_app


def test_api_saves_without_playing_and_default_releases(tmp_path, monkeypatch):
    monkeypatch.setenv('AGI_LIGHTING_CATALOG', str(tmp_path / 'lighting.md'))
    device = Mock()
    device.set_effect.return_value = {'active': True, 'connected': True}
    device.clear_effect.return_value = {'active': False, 'connected': False}
    with TestClient(create_app(device)) as client:
        catalog = client.get('/api/lighting/catalog').json()
        assert len(catalog['effects']) == 18
        assert 'pumpkin_green' in catalog['effects']
        for name in catalog['effects']:
            assert client.put('/api/lighting', json={'preset': name}).status_code == 200
        device.set_effect.reset_mock()
        assert client.put('/api/lighting/catalog', json={
            'name': 'hello', 'effect': {'start_color': '#AABBCC'},
            'reason': 'My greeting', 'meaning': 'Hello there',
        }).status_code == 200
        device.set_effect.assert_not_called()
        assert client.put('/api/lighting', json={'preset': 'hello'}).status_code == 200
        assert device.set_effect.call_args.args[0].meaning == 'Hello there'
        device.clear_effect.reset_mock()
        result = client.put('/api/lighting', json={'preset': 'default', 'reason': 'Normal again'})
        assert result.json()['selected'] == 'default'
        device.clear_effect.assert_called_once()
        for payload in ([], {'brightness': 3}, {'unknown': 1}, {'rhythm': 'morse'}, {'preset': 'missing'}):
            assert client.put('/api/lighting', json=payload).status_code == 422
        assert client.put('/api/lighting/catalog', json={'name': '../escape', 'effect': {}}).status_code == 422
        device.set_effect.side_effect = RuntimeError('SDK unavailable')
        assert client.put('/api/lighting', json={'preset': 'disco'}).status_code == 503
    device.close.assert_called_once()


def test_effect_holds_device_until_stopped_or_expired(tmp_path, monkeypatch):
    path = tmp_path / 'device.lock'
    monkeypatch.setenv('AGI_OPENRGB_LOCK_PATH', str(path))
    rgb = LightingDevice()
    rgb._thread = Mock(is_alive=lambda: True)
    with patch.object(rgb, '_write'):
        rgb.set_effect(LightingEffect(rhythm='morse', morse_text='HELLO'))
        assert rgb.status()['remaining_seconds'] is None
        assert rgb.status()['morse_message_seconds'] > 1
        with path.open('a') as contender:
            with pytest.raises(BlockingIOError):
                fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
            rgb.clear_effect()
            fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
        rgb.set_effect(LightingEffect(duration_seconds=.1))
        rgb._started -= 1
        rgb._tick()
        assert not rgb.status()['active']
        with path.open('a') as contender:
            fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_busy_device_and_failed_write_do_not_claim_success(tmp_path, monkeypatch):
    path = tmp_path / 'device.lock'
    monkeypatch.setenv('AGI_OPENRGB_LOCK_PATH', str(path))
    rgb = LightingDevice()
    rgb._thread = Mock(is_alive=lambda: True)
    with path.open('a') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match='busy'):
            rgb.set_effect(LightingEffect())
        assert not rgb.status()['active']
    with patch.object(rgb, '_write', side_effect=OSError('Disconnected')):
        with pytest.raises(RuntimeError, match='Disconnected'):
            rgb.set_effect(LightingEffect())
    assert not rgb.status()['active']
    with path.open('a') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
