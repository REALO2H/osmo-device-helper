from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
)
from PySide6.QtCore import Qt


class StatusPanel(QGroupBox):
    def __init__(self):
        super().__init__("Device Status")

        self.device_status_label = QLabel("-")
        self.owner_label = QLabel("-")
        self.reserved_label = QLabel("-")
        self.used_label = QLabel("-")
        self.remaining_label = QLabel("-")
        self.message_label = QLabel("-")

        layout = QGridLayout(self)

        layout.addWidget(QLabel("Device status:"), 0, 0)
        layout.addWidget(self.device_status_label, 0, 1)

        layout.addWidget(QLabel("Current owner:"), 1, 0)
        layout.addWidget(self.owner_label, 1, 1)

        layout.addWidget(QLabel("Reserved ports:"), 2, 0)
        layout.addWidget(self.reserved_label, 2, 1)

        layout.addWidget(QLabel("Used ports:"), 3, 0)
        layout.addWidget(self.used_label, 3, 1)

        layout.addWidget(QLabel("Remaining ports:"), 4, 0)
        layout.addWidget(self.remaining_label, 4, 1)

        layout.addWidget(QLabel("Message:"), 5, 0)
        layout.addWidget(self.message_label, 5, 1)

    def update_state(self, state):
        self.device_status_label.setText(str(state.device_status))
        self.owner_label.setText(state.owner_user or "-")
        self.reserved_label.setText(str(state.reserved_ports))
        self.used_label.setText(str(state.used_ports))
        self.remaining_label.setText(str(state.remaining_ports))
        self.message_label.setText(state.message or "-")


class ControlPanel(QGroupBox):
    def __init__(self):
        super().__init__("Actions")

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 100)
        self.port_spin.setValue(1)

        self.reserve_btn = QPushButton("Reserve Device")
        self.release_btn = QPushButton("Release My Queue")
        self.force_release_btn = QPushButton("Force Release (Admin)")
        self.simulate_progress_btn = QPushButton("Simulate One Port Finished")
        self.simulate_other_user_btn = QPushButton("Demo: Busy By Other User")
        self.make_free_btn = QPushButton("Demo: Make Device Free")

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Ports to reserve:"))
        row1.addWidget(self.port_spin)
        row1.addWidget(self.reserve_btn)
        row1.addWidget(self.release_btn)

        row2 = QHBoxLayout()
        row2.addWidget(self.force_release_btn)
        row2.addWidget(self.simulate_progress_btn)
        row2.addWidget(self.simulate_other_user_btn)
        row2.addWidget(self.make_free_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(row1)
        layout.addLayout(row2)


class ResultsPanel(QGroupBox):
    def __init__(self):
        super().__init__("Recent Measurements")

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Port", "Lot Number", "Value", "Unit", "Timestamp", "Operator"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)

    def update_results(self, results):
        self.table.setRowCount(len(results))
        for row_idx, result in enumerate(results):
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(result.port)))
            self.table.setItem(row_idx, 1, QTableWidgetItem(result.lot_number))
            self.table.setItem(row_idx, 2, QTableWidgetItem(result.value))
            self.table.setItem(row_idx, 3, QTableWidgetItem(result.unit))
            self.table.setItem(row_idx, 4, QTableWidgetItem(result.timestamp))
            self.table.setItem(row_idx, 5, QTableWidgetItem(result.operator))


class LogPanel(QGroupBox):
    def __init__(self):
        super().__init__("Info Log")
        self.text = QTextEdit()
        self.text.setReadOnly(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self.text)

    def append(self, message: str):
        self.text.append(message)