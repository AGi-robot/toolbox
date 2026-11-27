import unittest
from unittest.mock import patch
import httpx
from agi_toolbox.lighting import LightingClient


class ClientTests(unittest.TestCase):
    def test_methods_and_effect_payload(self):
        rgb = LightingClient('http://localhost:8854/')
        with patch('agi_toolbox.lighting.httpx.put') as put:
            put.return_value = httpx.Response(200, json={'active': True}, request=httpx.Request('PUT', rgb.url))
            self.assertTrue(rgb.set_effect(brightness=.2, reason='A soft light')['active'])
            put.assert_called_once_with(rgb.url, json={'brightness': .2, 'reason': 'A soft light'}, timeout=5)
        with patch('agi_toolbox.lighting.httpx.delete') as delete:
            delete.return_value = httpx.Response(200, json={'active': False}, request=httpx.Request('DELETE', rgb.url))
            self.assertFalse(rgb.stop(reason='Return to normal')['active'])

    def test_errors_propagate_to_tool_loop(self):
        rgb = LightingClient()
        with patch('agi_toolbox.lighting.httpx.put') as put:
            put.return_value = httpx.Response(503, request=httpx.Request('PUT', rgb.url))
            with self.assertRaises(httpx.HTTPStatusError):
                rgb.set_effect(reason='Try this colour')
