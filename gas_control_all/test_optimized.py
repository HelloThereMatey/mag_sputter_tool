#!/usr/bin/env python3
"""
Test the optimized gas flow controller performance vs CLI subprocess method.
"""

import asyncio
import time
import subprocess
import json
from optimized_controller import OptimizedGasFlowController
from subprocess_controller import GasFlowController as SubprocessGasFlowController


def test_cli_subprocess_method(serial_port='/dev/ttyUSB0', unit_ids=['A', 'B', 'C']):
    """Test CLI subprocess method for MFC communication."""
    
    print("\n🚀 Testing CLI Subprocess Method")
    print("=" * 50)
    
    results = {}
    
    for unit_id in unit_ids:
        print(f"\nTesting unit {unit_id}:")
        times = []
        readings = []
        
        for i in range(3):
            print(f"  Reading {i+1}: ", end="", flush=True)
            
            start = time.perf_counter()
            try:
                # Run CLI command using subprocess
                result = subprocess.run([
                    'alicat', serial_port, '--unit', unit_id
                ], capture_output=True, text=True, timeout=5)
                
                end = time.perf_counter()
                response_time = (end - start) * 1000
                times.append(response_time)
                
                if result.returncode == 0:
                    # Parse JSON output
                    data = json.loads(result.stdout.strip())
                    readings.append(data)
                    flow = data.get('mass_flow', 'N/A')
                    gas = data.get('gas', 'Unknown')
                    print(f"{response_time:6.1f}ms - Flow: {flow:>8.3f} ({gas})")
                else:
                    print(f"{response_time:6.1f}ms - ERROR: {result.stderr.strip()}")
                    
            except subprocess.TimeoutExpired:
                end = time.perf_counter()
                response_time = (end - start) * 1000
                print(f"{response_time:6.1f}ms - TIMEOUT")
            except Exception as e:
                end = time.perf_counter()
                response_time = (end - start) * 1000
                print(f"{response_time:6.1f}ms - ERROR: {str(e)[:30]}...")
        
        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            print(f"  Average: {avg_time:6.1f}ms (min: {min_time:.1f}ms, max: {max_time:.1f}ms)")
            
            results[unit_id] = {
                'times': times,
                'average': avg_time,
                'readings': readings
            }
        else:
            print(f"  No successful readings for unit {unit_id}")
            results[unit_id] = {'times': [], 'average': None, 'readings': []}
    
    return results


def test_subprocess_controller():
    """Test the new subprocess-based controller performance."""
    
    # Example config (adjust for your setup)
    config = {
        'mfcs': {
            'Ar': {
                'unit_id': 'A',
                'serial_port': '/dev/ttyUSB0',
                'max_flow': 100.0,
                'gas_type': 'Ar',
                'enabled': True
            },
            'N2': {
                'unit_id': 'B', 
                'serial_port': '/dev/ttyUSB0',
                'max_flow': 100.0,
                'gas_type': 'N2',
                'enabled': True
            },
            'O2': {
                'unit_id': 'C',
                'serial_port': '/dev/ttyUSB0', 
                'max_flow': 100.0,
                'gas_type': 'O2',
                'enabled': True
            }
        },
        'cli_timeout': 3.0,  # CLI command timeout
        'max_retries': 2,    # Retries for failed commands
        'read_interval': 10.0,  # Background reading interval
        'auto_read_enabled': False  # Disable for testing
    }
    
    print("🚀 Testing Subprocess Gas Flow Controller")
    print("=" * 50)
    
    # Create controller
    controller = SubprocessGasFlowController(config)
    results = {}
    
    try:
        # Start controller
        if not controller.start():
            print("❌ Failed to start subprocess controller")
            return results
        
        print("✅ Subprocess controller started")
        time.sleep(1)  # Let it initialize
        
        # Test reading performance
        print(f"\n📊 Testing Subprocess Controller Reading Performance:")
        for channel in ['Ar', 'N2', 'O2']:
            times = []
            print(f"\nChannel {channel}:")
            
            for i in range(3):
                start = time.perf_counter()
                reading = controller.get_reading(channel)
                end = time.perf_counter()
                
                response_time = (end - start) * 1000
                times.append(response_time)
                
                if reading:
                    print(f"  Reading {i+1}: {response_time:6.1f}ms - Flow: {reading.mass_flow:6.3f} ({reading.gas})")
                else:
                    print(f"  Reading {i+1}: {response_time:6.1f}ms - ERROR")
            
            if times:
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)
                print(f"  Average: {avg_time:6.1f}ms (min: {min_time:.1f}ms, max: {max_time:.1f}ms)")
                results[channel] = {
                    'times': times,
                    'average': avg_time
                }
        
        # Test flow setting performance
        print(f"\n⚙️  Testing Subprocess Controller Flow Setting:")
        channel = 'Ar'
        
        for flow_rate in [1.0, 5.0, 0.0]:
            start = time.perf_counter()
            success = controller.set_flow_rate(channel, flow_rate)
            end = time.perf_counter()
            
            response_time = (end - start) * 1000
            status = "✅ SUCCESS" if success else "❌ FAILED"
            print(f"  Set {flow_rate:4.1f} sccm: {response_time:6.1f}ms - {status}")
            
            # Brief delay between commands
            time.sleep(0.5)
        
    finally:
        print(f"\n🛑 Stopping subprocess controller...")
        controller.stop()
        print("✅ Subprocess controller stopped")
    
    return results
    """Test CLI subprocess method for flow control."""
    
    print(f"\n⚙️  Testing CLI Subprocess Flow Control (Unit {unit_id})")
    print("=" * 60)
    
    flow_rates = [1.0, 5.0, 0.0]
    
    for flow_rate in flow_rates:
        print(f"Setting flow to {flow_rate:4.1f} sccm: ", end="", flush=True)
        
        start = time.perf_counter()
        try:
            # Set flow rate using CLI
            result = subprocess.run([
                'alicat', serial_port, 
                '--unit', unit_id,
                '--set-flow-rate', str(flow_rate)
            ], capture_output=True, text=True, timeout=5)
            
            end = time.perf_counter()
            response_time = (end - start) * 1000
            
            if result.returncode == 0:
                # Parse the response to verify
                data = json.loads(result.stdout.strip())
                actual_setpoint = data.get('setpoint', 'N/A')
                print(f"{response_time:6.1f}ms - ✅ Setpoint: {actual_setpoint}")
            else:
                print(f"{response_time:6.1f}ms - ❌ ERROR: {result.stderr.strip()}")
                
        except subprocess.TimeoutExpired:
            end = time.perf_counter()
            response_time = (end - start) * 1000
            print(f"{response_time:6.1f}ms - ⏰ TIMEOUT")
        except Exception as e:
            end = time.perf_counter()
            response_time = (end - start) * 1000
            print(f"{response_time:6.1f}ms - ❌ ERROR: {str(e)[:30]}...")
        
        # Brief delay between commands
        time.sleep(0.5)


def test_optimized_controller():
    """Test the optimized controller performance."""
    
    # Example config (adjust for your setup)
    config = {
        'mfcs': {
            'Ar': {
                'unit_id': 'A',
                'serial_port': '/dev/ttyUSB0',
                'max_flow': 100.0,
                'gas_type': 'Ar',
                'enabled': True
            },
            'N2': {
                'unit_id': 'B', 
                'serial_port': '/dev/ttyUSB0',
                'max_flow': 100.0,
                'gas_type': 'N2',
                'enabled': True
            },
            'O2': {
                'unit_id': 'C',
                'serial_port': '/dev/ttyUSB0', 
                'max_flow': 100.0,
                'gas_type': 'O2',
                'enabled': True
            }
        },
        'default_timeout': 1.0,  # Optimized timeout
        'max_retries': 2
    }
    
    print("� Testing Optimized Gas Flow Controller")
    print("=" * 50)
    
    # Create controller
    controller = OptimizedGasFlowController(config)
    results = {}
    
    try:
        # Start controller
        if not controller.start():
            print("❌ Failed to start controller")
            return results
        
        print("✅ Controller started")
        time.sleep(1)  # Let it initialize
        
        # Test reading performance
        print(f"\n📊 Testing Optimized Controller Reading Performance:")
        for channel in ['Ar', 'N2', 'O2']:
            times = []
            print(f"\nChannel {channel}:")
            
            for i in range(3):
                start = time.perf_counter()
                reading = controller.get_reading(channel)
                end = time.perf_counter()
                
                response_time = (end - start) * 1000
                times.append(response_time)
                
                if reading:
                    print(f"  Reading {i+1}: {response_time:6.1f}ms - Flow: {reading.mass_flow:6.3f}")
                else:
                    print(f"  Reading {i+1}: {response_time:6.1f}ms - ERROR")
            
            if times:
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)
                print(f"  Average: {avg_time:6.1f}ms (min: {min_time:.1f}ms, max: {max_time:.1f}ms)")
                results[channel] = {
                    'times': times,
                    'average': avg_time
                }
        
        # Test flow setting performance
        print(f"\n⚙️  Testing Optimized Controller Flow Setting:")
        channel = 'Ar'
        
        for flow_rate in [1.0, 5.0, 0.0]:
            start = time.perf_counter()
            success = controller.set_flow_rate(channel, flow_rate)
            end = time.perf_counter()
            
            response_time = (end - start) * 1000
            status = "✅ SUCCESS" if success else "❌ FAILED"
            print(f"  Set {flow_rate:4.1f} sccm: {response_time:6.1f}ms - {status}")
            
            # Brief delay between commands
            time.sleep(0.5)
        
    finally:
        print(f"\n🛑 Stopping controller...")
        controller.stop()
        print("✅ Controller stopped")
    
    return results


def test_cli_subprocess_flow_control(serial_port='/dev/ttyUSB0', unit_id='A'):
    """Test CLI subprocess method for flow control."""
    
    print(f"\n⚙️  Testing CLI Subprocess Flow Control (Unit {unit_id})")
    print("=" * 60)
    
    flow_rates = [1.0, 5.0, 0.0]
    
    for flow_rate in flow_rates:
        print(f"Setting flow to {flow_rate:4.1f} sccm: ", end="", flush=True)
        
        start = time.perf_counter()
        try:
            # Set flow rate using CLI
            result = subprocess.run([
                'alicat', serial_port, 
                '--unit', unit_id,
                '--set-flow-rate', str(flow_rate)
            ], capture_output=True, text=True, timeout=5)
            
            end = time.perf_counter()
            response_time = (end - start) * 1000
            
            if result.returncode == 0:
                # Parse the response to verify
                data = json.loads(result.stdout.strip())
                actual_setpoint = data.get('setpoint', 'N/A')
                print(f"{response_time:6.1f}ms - ✅ Setpoint: {actual_setpoint}")
            else:
                print(f"{response_time:6.1f}ms - ❌ ERROR: {result.stderr.strip()}")
                
        except subprocess.TimeoutExpired:
            end = time.perf_counter()
            response_time = (end - start) * 1000
            print(f"{response_time:6.1f}ms - ⏰ TIMEOUT")
        except Exception as e:
            end = time.perf_counter()
            response_time = (end - start) * 1000
            print(f"{response_time:6.1f}ms - ❌ ERROR: {str(e)[:30]}...")
        
        # Brief delay between commands
        time.sleep(0.5)


def performance_comparison():
    """Compare performance between all three methods."""
    
    print("🏁 COMPREHENSIVE PERFORMANCE COMPARISON")
    print("=" * 80)
    
    # Test all three methods
    print("\n1️⃣  Testing Direct CLI Subprocess Calls...")
    cli_results = test_cli_subprocess_method('/dev/ttyUSB0', ['A', 'B', 'C'])
    
    print("\n2️⃣  Testing New Subprocess Controller...")
    subprocess_results = test_subprocess_controller()
    
    print("\n3️⃣  Testing Original Optimized Controller...")
    controller_results = test_optimized_controller()
    
    # Flow control comparison
    print("\n4️⃣  Testing CLI Subprocess Flow Control...")
    test_cli_subprocess_flow_control('/dev/ttyUSB0', 'A')
    
    # Summary comparison
    print("\n" + "=" * 80)
    print("📊 PERFORMANCE SUMMARY")
    print("=" * 80)
    print(f"{'Method':<30} {'Unit':<4} {'Avg Time':<10} {'Min Time':<10} {'Max Time':<10}")
    print("-" * 80)
    
    # Direct CLI results
    for unit_id, data in cli_results.items():
        if data['average'] is not None:
            times = data['times']
            print(f"{'Direct CLI':<30} {unit_id:<4} {data['average']:<10.1f} {min(times):<10.1f} {max(times):<10.1f}")
    
    # Subprocess controller results
    for channel, data in subprocess_results.items():
        if 'average' in data:
            times = data['times']
            print(f"{'Subprocess Controller':<30} {channel:<4} {data['average']:<10.1f} {min(times):<10.1f} {max(times):<10.1f}")
    
    # Original controller results  
    for channel, data in controller_results.items():
        if 'average' in data:
            times = data['times']
            print(f"{'Original Async Controller':<30} {channel:<4} {data['average']:<10.1f} {min(times):<10.1f} {max(times):<10.1f}")
    
    # Calculate overall averages
    cli_averages = [data['average'] for data in cli_results.values() if data['average'] is not None]
    subprocess_averages = [data['average'] for data in subprocess_results.values() if 'average' in data]
    controller_averages = [data['average'] for data in controller_results.values() if 'average' in data]
    
    if cli_averages and subprocess_averages and controller_averages:
        cli_overall = sum(cli_averages) / len(cli_averages)
        subprocess_overall = sum(subprocess_averages) / len(subprocess_averages)
        controller_overall = sum(controller_averages) / len(controller_averages)
        
        print(f"\n🏆 PERFORMANCE RANKING:")
        results = [
            ('Direct CLI', cli_overall),
            ('Subprocess Controller', subprocess_overall), 
            ('Original Async Controller', controller_overall)
        ]
        results.sort(key=lambda x: x[1])  # Sort by time (lower is better)
        
        for i, (method, avg_time) in enumerate(results):
            if i == 0:
                print(f"   🥇 {method}: {avg_time:.1f}ms (FASTEST)")
            elif i == 1:
                speedup = avg_time / results[0][1]
                print(f"   🥈 {method}: {avg_time:.1f}ms ({speedup:.1f}x slower)")
            else:
                speedup = avg_time / results[0][1]
                print(f"   🥉 {method}: {avg_time:.1f}ms ({speedup:.1f}x slower)")
        
        print(f"\n📈 Expected Performance:")
        print(f"   If subprocess controller performs like direct CLI:")
        print(f"   Expected speedup vs async: {controller_overall/cli_overall:.1f}x faster")


if __name__ == "__main__":
    performance_comparison()