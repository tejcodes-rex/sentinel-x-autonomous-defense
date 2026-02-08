"""
SENTINEL-X: Autonomous Cyber-Physical Defense
Main Entry Point
"""

import sys
import os
import time
import subprocess
from dotenv import load_dotenv

from sentinel_engine import SentinelEngine
from utils import scavenge_processes

def main():
    """
    Orchestrates the startup of the Sentinel system.
    """
    print("\n" + "="*50)
    print("   SENTINEL-X: INDUSTRIAL DEFENSE INITIALIZING   ")
    print("="*50 + "\n")

    # 1. Environment Check
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[!] WARNING: GEMINI_API_KEY not found in .env")
        print("[!] System will run in LIMITED/READ-ONLY mode.")

    # 2. Process Cleanup
    print("[1/3] Scavenging for orphaned industrial processes...")
    scavenge_processes()
    time.sleep(1)

    # 3. Launch PLC Simulator
    print("[2/3] Launching Industrial PLC Simulator...")
    # Launch as a separate process (Using shell=True with 'start' for reliable window popping on Windows)
    try:
        if os.name == 'nt':
            subprocess.Popen(f'start "SENTINEL-X PLC SIMULATOR" {sys.executable} plc_simulator.py', shell=True)
        else:
            subprocess.Popen([sys.executable, "plc_simulator.py"])
    except Exception as e:
        print(f"[ERROR] Failed to launch PLC Simulator: {e}")
        sys.exit(1)
    
    time.sleep(3) # Wait for Modbus stack to bind

    # 4. Initialize Engine
    print("[3/3] Initializing Sentinel Reasoning Engine...")
    
    try:
        engine = SentinelEngine(
            api_key=api_key or "",
            camera_index=int(os.getenv("CAMERA_INDEX", 0)),
            plc_ip=os.getenv("PLC_IP", "localhost"),
            plc_port=int(os.getenv("PLC_PORT", 5020))
        )
        
        # Start the Engine
        engine.run()
        
    except KeyboardInterrupt:
        print("\n[!] SENTINEL-X SHUTDOWN INITIATED [BY USER]")
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
    finally:
        print("[INFO] Performing emergency cleanup...")
        scavenge_processes()
        print("[OK] Lockdown successful. System offline.")

if __name__ == "__main__":
    main()
