#!/usr/bin/env python3
"""System resource monitor for Raspberry Pi 5"""

import psutil
import subprocess
import time
from datetime import datetime

def get_rpi_temperature():
    """Get Raspberry Pi CPU/GPU temperature"""
    try:
        # CPU temperature
        result = subprocess.run(
            ['vcgencmd', 'measure_temp'],
            capture_output=True,
            text=True,
            timeout=2
        )
        cpu_temp = result.stdout.strip()
        
        # Throttling status
        result = subprocess.run(
            ['vcgencmd', 'get_throttled'],
            capture_output=True,
            text=True,
            timeout=2
        )
        throttled = result.stdout.strip()
        
        return cpu_temp, throttled
    except Exception as e:
        return f"Error: {e}", "Error"

def monitor():
    """Print resource usage every 5 seconds"""
    print("=" * 80)
    print("Raspberry Pi 5 - System Resource Monitor")
    print("=" * 80)
    print("Press Ctrl+C to stop\n")
    
    try:
        while True:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_freq = psutil.cpu_freq()
            
            # Memory
            memory = psutil.virtual_memory()
            
            # Disk
            disk = psutil.disk_usage('/')
            
            # Network
            net = psutil.net_io_counters()
            
            # Temperature
            cpu_temp, throttled = get_rpi_temperature()
            
            # Clear screen and print
            print(f"\n[{timestamp}]")
            print(f"CPU:        {cpu_percent:6.1f}% ({cpu_freq.current:.0f} MHz)")
            print(f"Memory:     {memory.percent:6.1f}% ({memory.used/1024/1024/1024:.1f}GB / {memory.total/1024/1024/1024:.1f}GB)")
            print(f"Disk:       {disk.percent:6.1f}% ({disk.used/1024/1024/1024:.1f}GB / {disk.total/1024/1024/1024:.1f}GB)")
            print(f"Temperature: {cpu_temp}")
            print(f"Throttled:   {throttled}")
            print(f"Network:    ↓{net.bytes_recv/1024/1024:.1f}MB ↑{net.bytes_sent/1024/1024:.1f}MB")
            
            # Check for overheating
            if "80" in cpu_temp or "throttled" in throttled.lower():
                print("⚠️  WARNING: System may be overheating or throttling!")
            
            time.sleep(5)
    
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped")

if __name__ == "__main__":
    # Install psutil if needed
    try:
        import psutil
    except ImportError:
        print("Installing psutil...")
        import subprocess
        subprocess.run(['pip3', 'install', 'psutil'], check=True)
        import psutil
    
    monitor()