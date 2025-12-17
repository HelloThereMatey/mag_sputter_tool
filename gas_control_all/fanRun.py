#!/usr/bin/env python3
"""Simple full-speed fan control for Raspberry Pi 5"""

import RPi.GPIO as GPIO
import time
import sys

FAN_PIN = 12  # GPIO 12 - adjust if your fan is on a different pin

def run_fan_full_speed():
    """Run fan at 100% speed continuously"""
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(FAN_PIN, GPIO.OUT)
        pwm = GPIO.PWM(FAN_PIN, 1000)  # 1kHz frequency
        pwm.start(100)  # 100% duty cycle = full speed
        
        print(f"✅ Fan running at FULL SPEED on GPIO {FAN_PIN}")
        print("Press Ctrl+C to stop\n")
        
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\nStopping fan...")
        pwm.stop()
        GPIO.cleanup()
        print("✅ Fan stopped")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure you're running with: sudo python3 fanControl.py")

if __name__ == "__main__":
    run_fan_full_speed()