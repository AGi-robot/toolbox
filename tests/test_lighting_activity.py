"""Response reporting renews a lease off the chat thread and always attempts stop."""
from threading import Event
from unittest.mock import Mock, patch

import httpx

from agi_toolbox.lighting_activity import ResponseLighting


def test_reporter_sends_ordered_start_renewal_stop():
    reporter = ResponseLighting('http://lighting')
    client = Mock()
    client.put.return_value.json.return_value = {'accepted': True}
    with patch('agi_toolbox.lighting_activity.httpx.Client') as factory, \
         patch.object(reporter._stop, 'wait', side_effect=[False, True]):
        factory.return_value.__enter__.return_value = client
        reporter._run()
    calls = [call.kwargs['json'] for call in client.put.call_args_list]
    assert [c['event'] for c in calls] == ['start', 'keepalive', 'stop']
    assert [c['sequence'] for c in calls] == [0, 1, 2]
    assert {c['stream_id'] for c in calls} == {reporter.stream_id}


def test_reporter_failure_is_contained_and_attempts_cleanup():
    errors = []
    reporter = ResponseLighting('http://lighting', on_error=errors.append)
    client = Mock()
    client.put.side_effect = httpx.ConnectError('offline')
    with patch('agi_toolbox.lighting_activity.httpx.Client') as factory:
        factory.return_value.__enter__.return_value = client
        reporter._run()
    assert len(errors) == 1
    assert [c.kwargs['json']['event'] for c in client.put.call_args_list] == ['start', 'stop']


def test_closed_reporter_does_not_start():
    reporter = ResponseLighting('http://lighting')
    reporter.close()
    with patch('agi_toolbox.lighting_activity.httpx.Client') as factory:
        reporter.start()
        reporter._run()
        factory.assert_not_called()
    assert reporter._thread is None


def test_network_wait_does_not_block_start_or_close():
    entered, release = Event(), Event()
    reporter = ResponseLighting('http://lighting')
    client = Mock()
    def send(*args, **kwargs):
        entered.set()
        release.wait(1)
        result = Mock()
        result.json.return_value = {'accepted': True}
        return result
    client.put.side_effect = send
    with patch('agi_toolbox.lighting_activity.httpx.Client') as factory:
        factory.return_value.__enter__.return_value = client
        reporter.start()
        try:
            assert entered.wait(1)
            reporter.close()  # returns while the network worker is still blocked
            assert reporter._thread.is_alive()
        finally:
            release.set()
            reporter._thread.join(timeout=2)
        assert not reporter._thread.is_alive()
