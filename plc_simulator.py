"""
SENTINEL-X Industrial PLC Simulator
Emulates a Siemens S7-1200 Modbus TCP Server for security verification.
"""

import random
import time
import logging
import threading
from pymodbus.server import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext

# --- CONFIGURATION ---
PLC_PORT = 5020
TICK_RATE = 0.5  # Seconds between register updates

# Disable verbose logging for cleaner demo performance
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.ERROR)

def register_updater(context: ModbusServerContext) -> None:
    """
    Simulates real-world sensor drift and industrial register updates.
    Updates HR 40001 (Temp) and 40002 (Pressure).
    """
    # Slave ID 0x01 (Unit ID 1 is standard), Holding Registers
    slave_id = 0x01
    register_type = 3 # Holding Registers
    
    while True:
        try:
            # Simulate base sensor values with industrial jitter
            temp_jitter = random.uniform(-0.15, 0.15)
            pres_jitter = random.uniform(-0.5, 0.5)
            
            scaled_temp = int((22.0 + temp_jitter) * 100)
            scaled_pres = int((45.0 + pres_jitter) * 10)
            
            # Use Unit ID 1 and Address 0 (confirmed by scanner)
            context[slave_id].setValues(register_type, 0, [scaled_temp, scaled_pres])
        except Exception as e:
            pass
        time.sleep(TICK_RATE)

def run_server() -> None:
    """
    Initializes and starts the Modbus TCP Stack.
    """
    # 1. Initialize Datastore (2 holding registers starting at address 0)
    store = ModbusSlaveContext(
        hr=ModbusSequentialDataBlock(0, [2200, 450])
    )
    context = ModbusServerContext(slaves={0x01: store}, single=False)

    # 2. Identity
    identity = ModbusDeviceIdentification()
    identity.VendorName = 'SENTINEL-X Defense'
    identity.ProductCode = 'SX-1200-PRO'
    identity.ProductName = 'Sentinel Industrial Controller'
    identity.ModelName = 'S7-Emulator'

    # 3. Start Updater Thread
    update_thread = threading.Thread(target=register_updater, args=(context,), daemon=True)
    update_thread.start()

    print(f"--- SENTINEL-X PLC SERVER ACTIVE [PORT {PLC_PORT}] ---")
    StartTcpServer(context=context, identity=identity, address=("0.0.0.0", PLC_PORT))

if __name__ == "__main__":
    try:
        run_server()
    except KeyboardInterrupt:
        print("\n--- PLC SERVER SHUTDOWN ---")
