"""
SENTINEL-X Core Reasoning Engine
Implements multimodal industrial defense using Gemini 3 Flash.
"""

import cv2
import time
import threading
import os
import psutil
import numpy as np
from google import genai
from PIL import Image
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.align import Align
from datetime import datetime
from typing import Optional, Dict, Any

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    from pymodbus.client.tcp import ModbusTcpClient

from utils import SentinelState, create_dashboard_layout

class SentinelEngine:
    """
    The orchestrator for visual reasoning, industrial telemetry, and host security.
    """
    def __init__(self, api_key: str, camera_index: int = 0, plc_ip: str = "localhost", plc_port: int = 5020):
        self.api_key = api_key
        self.camera_index = camera_index
        self.plc_ip = plc_ip
        self.plc_port = plc_port
        
        self.state = SentinelState()
        self.client: Optional[genai.Client] = None
        self.model_name: Optional[str] = None
        
        # Initialize Gemini Client if key provided
        if api_key and api_key != "YOUR_API_KEY":
            self.client = genai.Client(api_key=api_key)

    def _get_plc_pid(self) -> Optional[int]:
        """Find the PID of the PLC simulator process."""
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline')
                if cmdline and "plc_simulator.py" in " ".join(cmdline):
                    return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return None

    def modbus_loop(self) -> None:
        """
        Polls the Industrial PLC via Modbus TCP and executes kill-switch on lockdown.
        """
        mb_client = ModbusTcpClient(self.plc_ip, port=self.plc_port)
        plc_pid = None
        
        while True:
            snap = self.state.get_snapshot()
            
            # 1. Autonomous Kill Switch
            if snap["lockdown"]:
                if not plc_pid:
                    plc_pid = self._get_plc_pid()
                
                if plc_pid:
                    try:
                        p = psutil.Process(plc_pid)
                        p.kill()
                        self.state.add_log(f"[SENTINEL] PHYSICAL ISOLATION: PID {plc_pid} Terminated.")
                    except: pass
                
                mb_client.close()
                self.state.set_plc_status("ISOLATED (SAFE)")
                self.state.add_log("[SENTINEL] NETWORK CONNECTION SEVERED.")
                break
            
            # 2. Polling Logic
            try:
                if not mb_client.connect():
                    self.state.set_plc_status("OFFLINE")
                    time.sleep(2)
                    continue
                
                self.state.set_plc_status("ONLINE (MODBUS_TCP)")
                
                # Read HR 40001-40002 (Address 0 in 0-based systems)
                rr = mb_client.read_holding_registers(0, count=2, slave=1)
                if rr and not rr.isError():
                    real_temp = rr.registers[0] / 100.0
                    real_pres = rr.registers[1] / 10.0
                    
                    ts = datetime.now().strftime("%H:%M:%S")
                    log = f"[{ts}] TEMP: {real_temp:.2f}C | PRES: {real_pres:.1f} PSI | STATUS: OK"
                    self.state.add_log(log)
                else:
                    self.state.add_log("[MODBUS] COMMS ERROR")
            except Exception as e:
                self.state.add_log(f"[MODBUS EXCEPTION] {str(e)[:40]}")
            
            time.sleep(0.5)

    def telemetry_loop(self) -> None:
        """Monitors host system resources."""
        while not self.state.get_snapshot()["lockdown"]:
            try:
                cpu = psutil.cpu_percent(interval=1)
                ram = psutil.virtual_memory().percent
                self.state.update_host(cpu, ram)
            except: pass

    def vision_loop(self) -> None:
        """
        Multimodal reasoning loop: Cross-references physical world (camera) 
        against digital state (Modbus).
        """
        if not self.client:
            self.state.update_analysis("CRITICAL: NO API KEY CONFIGURED", "SECURE")
            return

        # Try various model versions for deployment flexibility
        candidates = ['gemini-3-flash-preview', 'gemini-2.0-flash', 'gemini-1.5-flash']
        for model in candidates:
            try:
                self.client.models.generate_content(model=model, contents="ping")
                self.model_name = model
                self.state.add_log(f"[VISION] Connected to {model}")
                break
            except: continue

        if not self.model_name:
            self.state.update_analysis("API ACCESS ERROR: CHECK MODEL AVAILABILITY", "SECURE")
            return

        cap = cv2.VideoCapture(self.camera_index)
        while not self.state.get_snapshot()["lockdown"]:
            ret, frame = cap.read()
            if not ret:
                time.sleep(1)
                continue
            
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb)
                
                prompt = (
                    "Role: Industrial Safety Agent. "
                    "Analyze environment for Physical-Digital Discrepancies. "
                    "Current Data: Normal operation. "
                    "If you see: Fire, Smoke, Mist, or Liquid when data says 'Normal', flag as ATTACK. "
                    "Format: Reasoning: <1 sentence> Verdict: <VERDICT: SECURE or VERDICT: ATTACK>"
                )
                
                # 429 Resilience
                for attempt in range(2):
                    try:
                        resp = self.client.models.generate_content(model=self.model_name, contents=[pil_img, prompt])
                        txt = resp.text.strip()
                        verdict = "ATTACK" if "VERDICT: ATTACK" in txt.upper() else "SECURE"
                        self.state.update_analysis(txt, verdict)
                        break
                    except Exception as e:
                        if "429" in str(e): 
                             time.sleep(2)
                             continue
                        raise e
            except Exception as e:
                self.state.update_analysis(f"REASONING DELAY: {str(e)[:30]}", "SECURE")
            
            time.sleep(2.5) # Balanced for free tier stability
        cap.release()

    def update_ui(self, layout: Any) -> None:
        """Renders the professional Sentinel dashboard."""
        snap = self.state.get_snapshot()
        
        # 1. Header
        if snap["lockdown"]:
            header = Panel(Align.center("🚨 CRITICAL DISCREPANCY: PHYSICAL ATTACK DETECTED"), style="bold white on red blink")
        else:
            style = "bold white on green" if "ONLINE" in snap["plc_status"] else "bold white on yellow"
            header = Panel(Align.center(f"SENTINEL-X | LINK: {snap['plc_status']}"), style=style)
        layout["header"].update(header)

        # 2. Host Stats
        table = Table.grid(expand=True)
        table.add_row("CPU:", f"{snap['host']['cpu']}%")
        table.add_row("RAM:", f"{snap['host']['ram']}%")
        table.add_row("NETWORK:", f"{self.plc_ip}:{self.plc_port}")
        layout["host_stats"].update(Panel(table, title="Kernel Telemetry", border_style="cyan"))

        # 3. Industrial Data
        log_text = Text()
        for l in snap["logs"]:
            log_text.append(l + "\n", style="bright_green")
        layout["ics_stream"].update(Panel(log_text, title="Industrial Register Stream", border_style="green"))

        # 4. Vision
        v_style = "red bold" if snap["lockdown"] else "yellow"
        layout["right"].update(Panel(snap["analysis"], title="Visual Reasoning Cortex", style=v_style, border_style="yellow"))

    def run(self) -> None:
        """Starts the multi-threaded defense systems."""
        threads = [
            threading.Thread(target=self.modbus_loop, daemon=True),
            threading.Thread(target=self.telemetry_loop, daemon=True),
            threading.Thread(target=self.vision_loop, daemon=True)
        ]
        for t in threads: t.start()

        layout = create_dashboard_layout()
        with Live(layout, refresh_per_second=4, screen=True):
            try:
                while True:
                    self.update_ui(layout)
                    time.sleep(0.1)
            except KeyboardInterrupt:
                pass
