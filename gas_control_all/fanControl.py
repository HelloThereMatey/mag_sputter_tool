#!/usr/bin/env python3
"""Manual fan control for Raspberry Pi 5"""

import RPi.GPIO as GPIO
import time
import sys

# RPi5 fan pin (GPIO 12 on Pi5, PWM capable)
FAN_PIN = 12
PWM_FREQUENCY = 25000  # 25 kHz (typical for RPi5 fan)

def setup_fan():
    """Initialize GPIO for fan control"""
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(FAN_PIN, GPIO.OUT)
        pwm = GPIO.PWM(FAN_PIN, PWM_FREQUENCY)
        pwm.start(0)  # Start at 0% duty cycle
        return pwm
    except Exception as e:
        print(f"❌ Failed to initialize fan: {e}")
        print("Make sure you're running with sudo!")
        sys.exit(1)

def test_fan_speed(pwm, speed_percent):
    """Test fan at specific speed"""
    print(f"Setting fan to {speed_percent}%...")
    pwm.ChangeDutyCycle(speed_percent)
    time.sleep(2)
    print(f"✅ Fan running at {speed_percent}%")

def interactive_control(pwm):
    """Interactive fan speed control"""
    print("\n" + "="*60)
    print("RPi5 Fan Control")
    print("="*60)
    print("Commands:")
    print("  0-100  : Set fan speed percentage")
    print("  test   : Run speed test sequence")
    print("  temp   : Show current temperature")
    print("  quit   : Exit")
    print("="*60 + "\n")
    
    try:
        while True:
            command = input("Enter command: ").strip().lower()
            
            if command == "quit":
                print("Turning off fan...")
                pwm.ChangeDutyCycle(0)
                break
            
            elif command == "temp":
                try:
                    import subprocess
                    result = subprocess.run(
                        ['vcgencmd', 'measure_temp'],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    print(f"Current temperature: {result.stdout.strip()}")
                except Exception as e:
                    print(f"Error reading temperature: {e}")
            
            elif command == "test":
                print("\nRunning fan speed test...")
                for speed in [25, 50, 75, 100, 50, 0]:
                    test_fan_speed(pwm, speed)
                    time.sleep(1)
                print("✅ Test complete\n")
            
            else:
                try:
                    speed = int(command)
                    if 0 <= speed <= 100:
                        test_fan_speed(pwm, speed)
                    else:
                        print("❌ Speed must be between 0-100")
                except ValueError:
                    print("❌ Invalid command")
    
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        pwm.ChangeDutyCycle(0)
    
    finally:
        GPIO.cleanup()
        print("✅ GPIO cleaned up")

def automatic_temp_control(pwm, min_temp=50, max_temp=80):
    """Automatically control fan based on temperature"""
    print(f"\n{'='*60}")
    print("Automatic Temperature-Based Fan Control")
    print(f"Temperature range: {min_temp}°C - {max_temp}°C")
    print("Press Ctrl+C to exit")
    print(f"{'='*60}\n")
    
    try:
        while True:
            try:
                import subprocess
                result = subprocess.run(
                    ['vcgencmd', 'measure_temp'],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                # Extract temperature from "temp=XX.X'C"
                temp_str = result.stdout.strip()
                temp = float(temp_str.split('=')[1].split("'")[0])
                
                # Calculate fan speed based on temperature
                if temp < min_temp:
                    speed = 0
                elif temp > max_temp:
                    speed = 100
                else:
                    # Linear interpolation between min and max
                    speed = int((temp - min_temp) / (max_temp - min_temp) * 100)
                
                pwm.ChangeDutyCycle(speed)
                status = "🟢" if speed < 50 else "🟡" if speed < 80 else "🔴"
                print(f"{status} {temp:.1f}°C → Fan: {speed}%")
                
                time.sleep(5)
            
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(5)
    
    except KeyboardInterrupt:
        print("\n\nStopping automatic control...")
        pwm.ChangeDutyCycle(0)
    
    finally:
        GPIO.cleanup()
        print("✅ GPIO cleaned up")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "auto":
            print("⚠️  Running automatic temperature control")
            print("This requires: sudo python3 fan_control.py auto\n")
            pwm = setup_fan()
            automatic_temp_control(pwm)
        elif sys.argv[1].isdigit():
            speed = int(sys.argv[1])
            if 0 <= speed <= 100:
                pwm = setup_fan()
                test_fan_speed(pwm, speed)
                print("\nKeeping fan at this speed. Press Ctrl+C to stop.")
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\nTurning off fan...")
                    pwm.ChangeDutyCycle(0)
                    GPIO.cleanup()
            else:
                print("❌ Speed must be between 0-100")
        else:
            print("Usage:")
            print("  sudo python3 fan_control.py          # Interactive mode")
            print("  sudo python3 fan_control.py 75       # Run at 75% speed")
            print("  sudo python3 fan_control.py auto     # Auto control based on temperature")
    else:
        pwm = setup_fan()
        interactive_control(pwm)