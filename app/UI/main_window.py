from datetime import datetime
import tkinter as tk
from tkinter import ttk as tkttk
from tkinter import messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from app.services.auth_service import AuthService
from app.services.mock_state_service import MockStateService
from app.services.worker_service import WorkerService
from app.config.settings import REFRESH_INTERVAL_MS
from app.UI import styles


class MainWindow(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=18)
        self.pack(fill=BOTH, expand=YES)

        self.user = AuthService.get_user_context()
        self.state_service = MockStateService()
        self.worker = WorkerService(self.state_service)

        self._build_layout()
        self._wire_actions()
        self._start_worker()

        # Poll worker queue from the main thread
        self.after(REFRESH_INTERVAL_MS, self._drain_worker_queue)

        # Initial state
        self.refresh_view(self.state_service.get_state())

        self.master.protocol("WM_DELETE_WINDOW", self._on_close)

    # --------------------------------------------------
    # Layout
    # --------------------------------------------------

    def _build_layout(self):
        # Header
        header = ttk.Frame(self)
        header.pack(fill=X, pady=(0, 12))

        title = ttk.Label(
            header,
            text="OSMO Device Helper",
            font=styles.TITLE_FONT,
        )
        title.pack(side=LEFT)

        role_text = "Admin" if self.user.is_admin else "Operator"
        user_badge = ttk.Label(
            header,
            text=f"User: {self.user.username}  |  Role: {role_text}",
            bootstyle=styles.role_bootstyle(self.user.is_admin),
            padding=(12, 8),
            font=styles.BADGE_FONT,
        )
        user_badge.pack(side=RIGHT)

        # Status area
        self.status_frame = ttk.Labelframe(self, text="Device Status", padding=14)
        self.status_frame.pack(fill=X, pady=(0, 12))

        self.device_box = self._create_kpi_box(self.status_frame, "Device Status", 0)
        self.owner_box = self._create_kpi_box(self.status_frame, "Current Owner", 1)
        self.reserved_box = self._create_kpi_box(self.status_frame, "Reserved Ports", 2)
        self.used_box = self._create_kpi_box(self.status_frame, "Used Ports", 3)
        self.remaining_box = self._create_kpi_box(self.status_frame, "Remaining Ports", 4)

        self.message_label = ttk.Label(
            self.status_frame,
            text="-",
            font=styles.SUBTITLE_FONT,
            anchor="w",
        )
        self.message_label.grid(row=1, column=0, columnspan=5, sticky="ew", padx=6, pady=(10, 0))

        for i in range(5):
            self.status_frame.columnconfigure(i, weight=1)

        # Actions
        self.actions_frame = ttk.Labelframe(self, text="Actions", padding=14)
        self.actions_frame.pack(fill=X, pady=(0, 12))

        self.port_var = tk.IntVar(value=1)

        ttk.Label(self.actions_frame, text="Ports to reserve:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.port_spin = ttk.Spinbox(self.actions_frame, from_=1, to=100, textvariable=self.port_var, width=8)
        self.port_spin.grid(row=0, column=1, sticky="w")

        self.reserve_btn = ttk.Button(self.actions_frame, text="Reserve Device", bootstyle="success")
        self.release_btn = ttk.Button(self.actions_frame, text="Release My Queue", bootstyle="warning")
        self.force_release_btn = ttk.Button(self.actions_frame, text="Force Release (Admin)", bootstyle="danger")
        self.simulate_progress_btn = ttk.Button(self.actions_frame, text="Simulate One Port Finished", bootstyle="info")
        self.simulate_other_user_btn = ttk.Button(self.actions_frame, text="Demo: Busy by Other User", bootstyle="secondary")
        self.make_free_btn = ttk.Button(self.actions_frame, text="Demo: Make Device Free", bootstyle="primary")

        self.reserve_btn.grid(row=0, column=2, padx=8, pady=6, sticky="ew")
        self.release_btn.grid(row=0, column=3, padx=8, pady=6, sticky="ew")
        self.force_release_btn.grid(row=0, column=4, padx=8, pady=6, sticky="ew")

        self.simulate_progress_btn.grid(row=1, column=2, padx=8, pady=6, sticky="ew")
        self.simulate_other_user_btn.grid(row=1, column=3, padx=8, pady=6, sticky="ew")
        self.make_free_btn.grid(row=1, column=4, padx=8, pady=6, sticky="ew")

        self.actions_frame.columnconfigure(2, weight=1)
        self.actions_frame.columnconfigure(3, weight=1)
        self.actions_frame.columnconfigure(4, weight=1)

        # Content area
        content = ttk.Panedwindow(self, orient=HORIZONTAL)
        content.pack(fill=BOTH, expand=YES)

        left = ttk.Frame(content)
        right = ttk.Frame(content)

        content.add(left, weight=3)
        content.add(right, weight=2)

        # Results panel
        results_frame = ttk.Labelframe(left, text="Recent Measurements", padding=14)
        results_frame.pack(fill=BOTH, expand=YES)

        columns = ("port", "lot_number", "value", "unit", "timestamp", "operator")
        self.results_tree = tkttk.Treeview(results_frame, columns=columns, show="headings", height=10)

        column_config = [
            ("port", "Port", 70),
            ("lot_number", "Lot Number", 140),
            ("value", "Value", 100),
            ("unit", "Unit", 110),
            ("timestamp", "Timestamp", 180),
            ("operator", "Operator", 140),
        ]

        for col, title, width in column_config:
            self.results_tree.heading(col, text=title)
            self.results_tree.column(col, width=width, anchor="center")

        yscroll = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=yscroll.set)

        self.results_tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        results_frame.rowconfigure(0, weight=1)
        results_frame.columnconfigure(0, weight=1)

        # Log panel
        log_frame = ttk.Labelframe(right, text="Activity Log", padding=14)
        log_frame.pack(fill=BOTH, expand=YES)

        self.log_text = tk.Text(
            log_frame,
            height=16,
            wrap="word",
            font=styles.LOG_FONT,
            bg="#1f1f1f",
            fg="#f1f1f1",
            insertbackground="#f1f1f1",
            relief="flat",
        )
        self.log_text.pack(fill=BOTH, expand=YES)
        self.log_text.configure(state="disabled")

    def _create_kpi_box(self, master, title, column):
        frame = ttk.Frame(master, padding=14)
        frame.grid(row=0, column=column, padx=6, pady=6, sticky="nsew")

        title_label = ttk.Label(frame, text=title, font=styles.CARD_TITLE_FONT, anchor="w")
        title_label.pack(anchor="w")

        value_label = ttk.Label(frame, text="-", font=styles.CARD_VALUE_FONT, anchor="w")
        value_label.pack(anchor="w", pady=(6, 0))

        return {"frame": frame, "title": title_label, "value": value_label}

    # --------------------------------------------------
    # Worker / threading
    # --------------------------------------------------

    def _start_worker(self):
        self.worker.start()
        self.log("Background worker started.")

    def _drain_worker_queue(self):
        try:
            while True:
                msg_type, payload = self.worker.output_queue.get_nowait()

                if msg_type == "state_update":
                    self.refresh_view(payload)
                elif msg_type == "log":
                    self.log(str(payload))
        except Exception:
            pass
        finally:
            self.after(REFRESH_INTERVAL_MS, self._drain_worker_queue)

    def _on_close(self):
        self.worker.stop()
        self.master.destroy()

    # --------------------------------------------------
    # Logging
    # --------------------------------------------------

    def log(self, text):
        now = datetime.now().strftime("%H:%M:%S")
        line = f"[{now}] {text}\n"

        self.log_text.configure(state="normal")
        self.log_text.insert("end", line)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # --------------------------------------------------
    # State refresh
    # --------------------------------------------------

    def refresh_view(self, state):
        self.device_box["value"].configure(text=str(state.device_status))
        self.owner_box["value"].configure(text=state.owner_user or "-")
        self.reserved_box["value"].configure(text=str(state.reserved_ports))
        self.used_box["value"].configure(text=str(state.used_ports))
        self.remaining_box["value"].configure(text=str(state.remaining_ports))
        self.message_label.configure(text=state.message or "-")

        self._refresh_results(state.recent_results)

        is_owner = state.owner_user == self.user.username
        is_free = state.device_status == "free" or not state.owner_user

        self.release_btn.configure(state=(NORMAL if is_owner else DISABLED))
        self.force_release_btn.configure(state=(NORMAL if self.user.is_admin else DISABLED))
        self.simulate_progress_btn.configure(state=(NORMAL if is_owner or self.user.is_admin else DISABLED))
        self.reserve_btn.configure(state=(NORMAL if is_free or is_owner else DISABLED))

    def _refresh_results(self, results):
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        for r in results:
            self.results_tree.insert(
                "",
                "end",
                values=(
                    r.port,
                    r.lot_number,
                    r.value,
                    r.unit,
                    r.timestamp,
                    r.operator,
                ),
            )

    # --------------------------------------------------
    # Actions
    # --------------------------------------------------

    def _wire_actions(self):
        self.reserve_btn.configure(command=self.on_reserve)
        self.release_btn.configure(command=self.on_release)
        self.force_release_btn.configure(command=self.on_force_release)
        self.simulate_progress_btn.configure(command=self.on_simulate_progress)
        self.simulate_other_user_btn.configure(command=self.on_simulate_other_user)
        self.make_free_btn.configure(command=self.on_make_free)

    def on_reserve(self):
        try:
            ports = int(self.port_var.get())
        except Exception:
            messagebox.showwarning("Invalid Input", "Please enter a valid number of ports.")
            return

        ok, msg = self.state_service.reserve_ports(self.user, ports)
        if not ok:
            messagebox.showwarning("Reserve Failed", msg)

        self.log(msg)

    def on_release(self):
        ok, msg = self.state_service.release_queue(self.user)
        if not ok:
            messagebox.showwarning("Release Failed", msg)

        self.log(msg)

    def on_force_release(self):
        ok, msg = self.state_service.force_release(self.user)
        if not ok:
            messagebox.showwarning("Force Release Failed", msg)

        self.log(msg)

    def on_simulate_progress(self):
        ok, msg = self.state_service.simulate_port_consumed(self.user)
        if not ok:
            messagebox.showwarning("Simulation Failed", msg)

        self.log(msg)

    def on_simulate_other_user(self):
        self.state_service.simulate_busy_by_other_user()
        self.log("Loaded demo state: busy by another user.")

    def on_make_free(self):
        self.state_service.make_free()
        self.log("Loaded demo state: device free.")
