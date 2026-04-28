import threading
import queue
import time
from app.config.settings import WORKER_POLL_INTERVAL_SEC


class WorkerService:
    """
    Background worker that NEVER touches GUI widgets directly.
    It polls the service state and pushes updates to a thread-safe queue.
    """

    def __init__(self, state_service):
        self.state_service = state_service
        self.output_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._thread = None
        self._last_state_signature = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _run(self):
        self.output_queue.put(("log", "Background worker started."))

        while not self._stop_event.is_set():
            state = self.state_service.get_state()

            signature = (
                state.device_status,
                state.owner_user,
                state.reserved_ports,
                state.used_ports,
                state.remaining_ports,
                state.queue_locked,
                state.message,
                len(state.recent_results),
                tuple(
                    (r.port, r.timestamp, r.operator, r.value)
                    for r in state.recent_results[:10]
                ),
            )

            if signature != self._last_state_signature:
                self.output_queue.put(("state_update", state))
                self._last_state_signature = signature

            time.sleep(WORKER_POLL_INTERVAL_SEC)