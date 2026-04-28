from datetime import datetime
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QMessageBox

from app.config.settings import APP_TITLE
from app.services.auth_service import AuthService
from app.services.mock_state_service import MockStateService
from app.ui.panels import StatusPanel, ControlPanel, ResultsPanel, LogPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.user = AuthService.get_user_context()
        self.state_service = MockStateService()

        self.setWindowTitle(APP_TITLE)
        self.resize(900, 650)

        self._build_ui()
        self.refresh_view()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        self.user_label = QLabel(
            f"Current user: {self.user.username} | "
            f"Admin: {'Yes' if self.user.is_admin else 'No'}"
        )
        self.user_label.setStyleSheet("font-size: 14px; font-weight: bold;")

        self.status_panel = StatusPanel()
        self.control_panel = ControlPanel()
        self.results_panel = ResultsPanel()
        self.log_panel = LogPanel()

        layout.addWidget(self.user_label)
        layout.addWidget(self.status_panel)
        layout.addWidget(self.control_panel)
        layout.addWidget(self.results_panel)
        layout.addWidget(self.log_panel)

        # Wire buttons
        self.control_panel.reserve_btn.clicked.connect(self.on_reserve)
        self.control_panel.release_btn.clicked.connect(self.on_release)
        self.control_panel.force_release_btn.clicked.connect(self.on_force_release)
        self.control_panel.simulate_progress_btn.clicked.connect(self.on_simulate_progress)
        self.control_panel.simulate_other_user_btn.clicked.connect(self.on_simulate_other_user)
        self.control_panel.make_free_btn.clicked.connect(self.on_make_free)

    def log(self, text: str):
        now = datetime.now().strftime("%H:%M:%S")
        self.log_panel.append(f"[{now}] {text}")

    def refresh_view(self):
        state = self.state_service.get_state()

        self.status_panel.update_state(state)
        self.results_panel.update_results(state.recent_results)

        is_owner = state.owner_user == self.user.username
        is_free = state.device_status == "free" or not state.owner_user

        self.control_panel.release_btn.setEnabled(is_owner)
        self.control_panel.force_release_btn.setEnabled(self.user.is_admin)
        self.control_panel.simulate_progress_btn.setEnabled(is_owner or self.user.is_admin)
        self.control_panel.reserve_btn.setEnabled(is_free or is_owner)

    def on_reserve(self):
        ports = self.control_panel.port_spin.value()
        ok, msg = self.state_service.reserve_ports(self.user, ports)
        if not ok:
            QMessageBox.warning(self, "Reserve Failed", msg)
        self.log(msg)
        self.refresh_view()

    def on_release(self):
        ok, msg = self.state_service.release_queue(self.user)
        if not ok:
            QMessageBox.warning(self, "Release Failed", msg)
        self.log(msg)
        self.refresh_view()

    def on_force_release(self):
        ok, msg = self.state_service.force_release(self.user)
        if not ok:
            QMessageBox.warning(self, "Force Release Failed", msg)
        self.log(msg)
        self.refresh_view()

    def on_simulate_progress(self):
        ok, msg = self.state_service.simulate_port_consumed(self.user)
        if not ok:
            QMessageBox.warning(self, "Simulation Failed", msg)
        self.log(msg)
        self.refresh_view()

    def on_simulate_other_user(self):
        self.state_service.simulate_busy_by_other_user()
        self.log("Loaded demo state: busy by another user.")
        self.refresh_view()

    def on_make_free(self):
        self.state_service.make_free()
        self.log("Loaded demo state: device free.")
        self.refresh_view()