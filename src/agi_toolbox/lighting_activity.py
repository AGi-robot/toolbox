"""Background response-activity reports; lighting failures never block text streaming."""
import threading
import uuid

import httpx


class ResponseLighting:
    def __init__(self, service_url, *, on_error=None):
        self.url = service_url.rstrip('/') + '/api/lighting/response'
        self.stream_id = uuid.uuid4().hex
        self.on_error = on_error or (lambda message: None)
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread is None and not self._stop.is_set():
            self._thread = threading.Thread(target=self._run, name='grace-response-lighting', daemon=True)
            self._thread.start()

    def close(self):
        # Do not join a network worker on the chat streaming thread. The worker
        # sends stop next; the service's three-second lease also bounds failures.
        self._stop.set()

    def _run(self):
        if self._stop.is_set():
            return
        sequence = 0
        try:
            with httpx.Client(timeout=0.5) as client:
                def send(event):
                    nonlocal sequence
                    try:
                        result = client.put(self.url, json={
                            'stream_id': self.stream_id, 'event': event, 'sequence': sequence,
                        })
                        result.raise_for_status()
                        return result.json().get('accepted', False)
                    finally:
                        sequence += 1
                if self._stop.is_set():
                    return
                try:
                    if not send('start'):
                        return
                    while not self._stop.wait(0.5):
                        if not send('keepalive'):
                            break
                finally:
                    send('stop')
        except Exception as error:
            self.on_error(f'Response lighting unavailable: {error}')
