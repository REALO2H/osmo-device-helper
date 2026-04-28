from datetime import datetime
from app.config.settings import MOCK_OTHER_USER
from app.models.state import QueueState, MeasurementResult, UserContext


class MockStateService:
    """
    Mock backend for GUI testing only.
    Later this can be replaced with a real shared-folder / supervisor-backed service.
    """

    def __init__(self):
        self.state = QueueState()

    def get_state(self) -> QueueState:
        return self.state

    def reserve_ports(self, user: UserContext, ports: int):
        if ports <= 0:
            return False, "Ports must be greater than 0."

        # Device already reserved by another user
        if self.state.owner_user and self.state.owner_user != user.username:
            return False, f"Device is currently being used by '{self.state.owner_user}'."

        self.state.device_status = "busy"
        self.state.owner_user = user.username
        self.state.reserved_ports = ports
        self.state.used_ports = 0
        self.state.remaining_ports = ports
        self.state.queue_locked = True
        self.state.message = f"Queue reserved for {user.username} ({ports} port(s))."
        self.state.recent_results = []

        return True, "Reservation successful."

    def release_queue(self, user: UserContext):
        if not self.state.owner_user:
            return False, "No active owner."

        if self.state.owner_user != user.username and not user.is_admin:
            return False, "You cannot release another user's queue."

        self._reset_state()
        return True, "Queue released."

    def force_release(self, user: UserContext):
        if not user.is_admin:
            return False, "You are not allowed to force release."

        self._reset_state()
        return True, "Queue force released."

    def simulate_port_consumed(self, user: UserContext):
        if self.state.owner_user != user.username and not user.is_admin:
            return False, "Only the owner (or admin) can simulate progress."

        if self.state.remaining_ports <= 0:
            return False, "No remaining ports."

        port_number = self.state.used_ports + 1
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.state.used_ports += 1
        self.state.remaining_ports -= 1

        result = MeasurementResult(
            port=port_number,
            lot_number=f"LOT-{datetime.now().strftime('%m%d')}",
            value=str(300 + port_number),
            unit="mOsm/kg",
            timestamp=now,
            operator=self.state.owner_user,
            flags="",
            error_or_comment=""
        )
        self.state.recent_results.insert(0, result)

        if self.state.remaining_ports == 0:
            finished_user = self.state.owner_user
            self._reset_state()
            self.state.message = f"All reserved ports for {finished_user} have been used. Device is now free."
        else:
            self.state.message = (
                f"Measurement completed on port {port_number}. "
                f"{self.state.remaining_ports} port(s) remaining."
            )

        return True, "Simulated one completed measurement."

    def simulate_busy_by_other_user(self):
        self.state.device_status = "busy"
        self.state.owner_user = MOCK_OTHER_USER
        self.state.reserved_ports = 4
        self.state.used_ports = 1
        self.state.remaining_ports = 3
        self.state.queue_locked = True
        self.state.message = f"Device is currently in use by {MOCK_OTHER_USER}."

        self.state.recent_results = [
            MeasurementResult(
                port=1,
                lot_number="LOT-0427",
                value="322",
                unit="mOsm/kg",
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                operator=MOCK_OTHER_USER,
                flags="",
                error_or_comment=""
            )
        ]

    def make_free(self):
        self._reset_state()

    def _reset_state(self):
        self.state = QueueState()
