"""
SENTINEL-X Utilities
Provides shared services for state management, process handling, and UI layout.
"""

import os
import psutil
import threading
from datetime import datetime
from rich.layout import Layout
from typing import Dict, List, Any

class SentinelState:
    """
    Thread-safe global state for the Sentinel system.
    Maintains telemetry, visual analysis, and lockdown status.
    """
    def __init__(self):
        self.ics_logs: List[str] = []
        self.visual_analysis: str = "Initializing Industrial Defense..."
        self.verdict: str = "SECURE"
        self.lockdown: bool = False
        self.host_stats: Dict[str, float] = {"cpu": 0.0, "ram": 0.0}
        self.plc_status: str = "CONNECTING..."
        self._lock = threading.Lock()

    def update_host(self, cpu: float, ram: float) -> None:
        """Update host telemetry stats."""
        with self._lock:
            self.host_stats = {"cpu": cpu, "ram": ram}

    def add_log(self, log: str) -> None:
        """Add a new entry to the industrial log stream."""
        with self._lock:
            self.ics_logs.append(log)
            if len(self.ics_logs) > 50:
                self.ics_logs.pop(0)

    def update_analysis(self, text: str, verdict: str) -> None:
        """Update the visual analysis result and check for lockdown triggers."""
        with self._lock:
            self.visual_analysis = text
            self.verdict = verdict
            if verdict == "ATTACK":
                self.lockdown = True

    def set_plc_status(self, status: str) -> None:
        """Update the Modbus connection status."""
        with self._lock:
            self.plc_status = status

    def get_snapshot(self) -> Dict[str, Any]:
        """Return a thread-safe snapshot of the current system state."""
        with self._lock:
            return {
                "logs": list(self.ics_logs),
                "analysis": self.visual_analysis,
                "verdict": self.verdict,
                "lockdown": self.lockdown,
                "host": self.host_stats,
                "plc_status": self.plc_status
            }

def scavenge_processes(target_name: str = "plc_simulator.py") -> None:
    """
    Clean up any orphaned industrial processes to prevent port conflicts.
    """
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline')
            if cmdline and target_name in " ".join(cmdline):
                p = psutil.Process(proc.info['pid'])
                p.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

def create_dashboard_layout() -> Layout:
    """
    Factory function for the Rich dashboard layout.
    """
    layout = Layout(name="root")
    layout.split(
        Layout(name="header", size=3),
        Layout(name="body", ratio=1)
    )
    layout["body"].split_row(
        Layout(name="left", ratio=1),
        Layout(name="right", ratio=1)
    )
    layout["left"].split_column(
        Layout(name="host_stats", size=7),
        Layout(name="ics_stream")
    )
    return layout
