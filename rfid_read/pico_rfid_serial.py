"""
RFID Card Reader for Raspberry Pi Pico with USB Serial Output
Reads RFID cards and sends card IDs to PC via USB serial (appears as COM port).

Hardware Setup:
  - Pico connected to PC via USB cable
  - USB serial appears as COM5 on Windows
  - RFID module connected via I2C (SDA/SCL pins)

Usage:
  1. Save this as main.py on the Pico
  2. Pico will auto-run on power-up via boot.py
  3. On PC, run: python serial_test.py
  4. Present RFID cards to the reader
"""

import time
from PiicoDev_RFID import PiicoDev_RFID
from PiicoDev_Unified import sleep_ms

# ===== Configuration =====
READ_INTERVAL_MS = 100     # Poll RFID reader every 100ms
DEBOUNCE_MS = 500          # Ignore same card for 500ms after first read

# ===== Initialize =====
rfid = PiicoDev_RFID()

last_card_id = None
last_read_time = 0
last_ready_msg_time = 0
READY_MSG_INTERVAL_MS = 10000  # Send ready message every 10 seconds

# Send startup message to USB serial
print("PICO_RFID_READY:v1.0")
last_ready_msg_time = time.ticks_ms()

# ===== Main loop =====
while True:
    current_time = time.ticks_ms()
    
    # Send ready message periodically (every 10 seconds)
    # This ensures the PC can always identify the Pico even if it connects late
    if (current_time - last_ready_msg_time) > READY_MSG_INTERVAL_MS:
        print("PICO_RFID_READY:v1.0")
        last_ready_msg_time = current_time
    
    if rfid.tagPresent():
        card_id = rfid.readID()
        
        # Debounce: only send if card is different or enough time has passed
        if card_id != last_card_id or (current_time - last_read_time) > DEBOUNCE_MS:
            # Send card ID to USB serial (PC reads via COM5)
            print(card_id)
            
            last_card_id = card_id
            last_read_time = current_time
    
    sleep_ms(READ_INTERVAL_MS)