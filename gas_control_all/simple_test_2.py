#!/usr/bin/env python3
"""
Simple Alicat MFC connectivity test script with response time measurements.

This script provides a basic test to verify communication with Alicat MFCs,
help identify common issues, and measure response times for performance analysis.
"""

import asyncio
import sys
import time
import statistics
from alicat import FlowController


async def measure_response_times(unit_id='A', serial_port='/dev/ttyUSB0', num_readings=10):
    """Measure response times for a specific MFC unit.
    
    Args:
        unit_id: Alicat unit ID (A, B, C, etc.)
        serial_port: Serial port path
        num_readings: Number of readings to take for averaging
    
    Returns:
        dict: Response time statistics
    """
    print(f"\n📊 Measuring response times for unit {unit_id}")
    print(f"   Port: {serial_port}")
    print(f"   Readings: {num_readings}")
    print("-" * 50)
    
    response_times = []
    successful_readings = 0
    
    try:
        # Create flow controller with reasonable timeout
        fc = FlowController(address=serial_port, unit=unit_id, timeout=2)
        
        for i in range(num_readings):
            print(f"Reading {i+1:2d}/{num_readings}: ", end="", flush=True)
            
            # Measure time for single reading
            start_time = time.perf_counter()
            try:
                result = await fc.get()
                end_time = time.perf_counter()
                
                response_time = (end_time - start_time) * 1000  # Convert to milliseconds
                response_times.append(response_time)
                successful_readings += 1
                
                print(f"{response_time:6.1f}ms - Flow: {result.get('mass_flow', 'N/A'):>8.3f}")
                
            except Exception as e:
                end_time = time.perf_counter()
                response_time = (end_time - start_time) * 1000
                print(f"{response_time:6.1f}ms - ❌ ERROR: {str(e)[:30]}...")
            
            # Small delay between readings
            await asyncio.sleep(0.1)
        
        await fc.close()
        
        # Calculate statistics
        if response_times:
            stats = {
                'unit_id': unit_id,
                'serial_port': serial_port,
                'successful_readings': successful_readings,
                'total_readings': num_readings,
                'success_rate': (successful_readings / num_readings) * 100,
                'min_time_ms': min(response_times),
                'max_time_ms': max(response_times),
                'avg_time_ms': statistics.mean(response_times),
                'median_time_ms': statistics.median(response_times),
                'std_dev_ms': statistics.stdev(response_times) if len(response_times) > 1 else 0,
                'all_times': response_times
            }
            
            print(f"\n📈 Statistics for unit {unit_id}:")
            print(f"   Success rate: {stats['success_rate']:.1f}% ({successful_readings}/{num_readings})")
            print(f"   Average time: {stats['avg_time_ms']:.1f} ms")
            print(f"   Median time:  {stats['median_time_ms']:.1f} ms")
            print(f"   Min time:     {stats['min_time_ms']:.1f} ms")
            print(f"   Max time:     {stats['max_time_ms']:.1f} ms")
            print(f"   Std dev:      {stats['std_dev_ms']:.1f} ms")
            
            return stats
        else:
            print(f"❌ No successful readings for unit {unit_id}")
            return None
            
    except Exception as e:
        print(f"❌ Failed to connect to unit {unit_id}: {e}")
        return None


async def benchmark_all_units(serial_port='/dev/ttyUSB0', num_readings=10):
    """Benchmark all MFC units and compare performance."""
    
    print("🚀 MFC Response Time Benchmark")
    print("=" * 60)
    print(f"Serial Port: {serial_port}")
    print(f"Readings per unit: {num_readings}")
    print()
    
    # Test each possible unit ID
    units_to_test = ['A', 'B', 'C', 'D', 'E']
    all_stats = []
    
    for unit_id in units_to_test:
        stats = await measure_response_times(unit_id, serial_port, num_readings)
        if stats:
            all_stats.append(stats)
    
    # Summary comparison
    if all_stats:
        print("\n" + "=" * 60)
        print("📊 PERFORMANCE SUMMARY")
        print("=" * 60)
        print(f"{'Unit':<4} {'Success%':<8} {'Avg(ms)':<8} {'Min(ms)':<8} {'Max(ms)':<8} {'StdDev':<8}")
        print("-" * 60)
        
        for stats in all_stats:
            print(f"{stats['unit_id']:<4} "
                  f"{stats['success_rate']:<8.1f} "
                  f"{stats['avg_time_ms']:<8.1f} "
                  f"{stats['min_time_ms']:<8.1f} "
                  f"{stats['max_time_ms']:<8.1f} "
                  f"{stats['std_dev_ms']:<8.1f}")
        
        # Find fastest and slowest
        fastest = min(all_stats, key=lambda x: x['avg_time_ms'])
        slowest = max(all_stats, key=lambda x: x['avg_time_ms'])
        
        print(f"\n🏆 Fastest unit: {fastest['unit_id']} ({fastest['avg_time_ms']:.1f} ms avg)")
        print(f"🐌 Slowest unit: {slowest['unit_id']} ({slowest['avg_time_ms']:.1f} ms avg)")
        
        if len(all_stats) > 1:
            overall_avg = statistics.mean([s['avg_time_ms'] for s in all_stats])
            print(f"📈 Overall average: {overall_avg:.1f} ms")
    
    return all_stats


async def quick_connectivity_scan(serial_port='/dev/ttyUSB0'):
    """Quick scan to find which units are connected."""
    
    print("🔍 Quick Connectivity Scan")
    print("-" * 40)
    
    units_found = []
    
    for unit_id in ['A', 'B', 'C', 'D', 'E']:
        print(f"Testing unit {unit_id}... ", end="", flush=True)
        
        start_time = time.perf_counter()
        try:
            # Create flow controller with short timeout for faster scanning
            fc = FlowController(address=serial_port, unit=unit_id, timeout=1)
            
            # Try to get a reading
            result = await fc.get()
            end_time = time.perf_counter()
            
            response_time = (end_time - start_time) * 1000
            print(f"✅ FOUND ({response_time:.0f}ms) - {result.get('gas', 'Unknown gas')}")
            units_found.append(unit_id)
            
            await fc.close()
            
        except Exception as e:
            end_time = time.perf_counter()
            response_time = (end_time - start_time) * 1000
            print(f"❌ No response ({response_time:.0f}ms)")
    
    print(f"\nFound {len(units_found)} MFC(s) at unit IDs: {units_found}")
    return units_found


async def test_specific_unit(unit_id='A', serial_port='/dev/ttyUSB0'):
    """Test a specific unit with detailed output and timing."""
    
    print(f"\n🔬 Detailed test for unit {unit_id}:")
    print("-" * 40)
    
    try:
        start_connect = time.perf_counter()
        async with FlowController(serial_port, unit=unit_id) as fc:
            end_connect = time.perf_counter()
            connect_time = (end_connect - start_connect) * 1000
            print(f"Connection time: {connect_time:.1f} ms")
            
            # Get readings multiple times with timing
            for i in range(3):
                start_read = time.perf_counter()
                result = await fc.get()
                end_read = time.perf_counter()
                read_time = (end_read - start_read) * 1000
                
                print(f"Reading {i+1} ({read_time:.1f}ms): {result}")
                await asyncio.sleep(0.5)
            
            # Try setting a small flow rate
            print("\nTesting flow control...")
            start_set = time.perf_counter()
            await fc.set_flow_rate(1.0)  # Set 1 sccm
            end_set = time.perf_counter()
            set_time = (end_set - start_set) * 1000
            print(f"Set flow command time: {set_time:.1f} ms")
            
            await asyncio.sleep(1)
            
            start_read = time.perf_counter()
            result = await fc.get()
            end_read = time.perf_counter()
            read_time = (end_read - start_read) * 1000
            print(f"After setting 1.0 sccm ({read_time:.1f}ms): {result}")
            
            # Return to zero
            start_zero = time.perf_counter()
            await fc.set_flow_rate(0.0)
            end_zero = time.perf_counter()
            zero_time = (end_zero - start_zero) * 1000
            print(f"Zero flow command time: {zero_time:.1f} ms")
            
            await asyncio.sleep(1)
            
            start_read = time.perf_counter()
            result = await fc.get()
            end_read = time.perf_counter()
            read_time = (end_read - start_read) * 1000
            print(f"After returning to 0 ({read_time:.1f}ms): {result}")
            
    except Exception as e:
        print(f"❌ Error testing unit {unit_id}: {e}")


def print_usage():
    """Print usage instructions."""
    print("\n" + "=" * 60)
    print("USAGE OPTIONS:")
    print("=" * 60)
    print("1. Quick scan:        python simple_test.py")
    print("2. Full benchmark:    python simple_test.py --benchmark")
    print("3. Single unit test:  python simple_test.py --unit A")
    print("4. Custom port:       python simple_test.py --port COM3")
    print("5. Custom readings:   python simple_test.py --benchmark --readings 20")
    print()
    print("Examples:")
    print("  python simple_test.py --benchmark --port /dev/ttyUSB0 --readings 15")
    print("  python simple_test.py --unit B --port COM5")
    print()


if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description='MFC Response Time Test')
    parser.add_argument('--port', default='/dev/ttyUSB0', 
                       help='Serial port (default: /dev/ttyUSB0)')
    parser.add_argument('--unit', type=str, 
                       help='Test specific unit ID (A, B, C, D, E)')
    parser.add_argument('--benchmark', action='store_true',
                       help='Run full benchmark on all units')
    parser.add_argument('--readings', type=int, default=10,
                       help='Number of readings for benchmark (default: 10)')
    
    args = parser.parse_args()
    
    # Adjust port for Windows if needed
    if sys.platform.startswith('win') and args.port.startswith('/dev/'):
        print("⚠️  Detected Windows but Unix-style port path.")
        print("   Consider using --port COM3, COM4, etc.")
        print()
    
    try:
        if args.unit:
            # Test specific unit
            print(f"Testing specific unit {args.unit} on {args.port}")
            asyncio.run(test_specific_unit(args.unit, args.port))
        elif args.benchmark:
            # Run full benchmark
            print(f"Running benchmark with {args.readings} readings per unit")
            asyncio.run(benchmark_all_units(args.port, args.readings))
        else:
            # Quick connectivity scan
            print("Running quick connectivity scan...")
            units_found = asyncio.run(quick_connectivity_scan(args.port))
            
            if units_found:
                print(f"\n✅ Found {len(units_found)} units. Run with --benchmark for detailed timing.")
            else:
                print("\n❌ No units found. Check your setup:")
                print("   • Verify serial port path")
                print("   • Check MFC power")
                print("   • Verify USB/serial converter")
                if not sys.platform.startswith('win'):
                    print("   • Check permissions: sudo usermod -a -G dialout $USER")
        
        print_usage()
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()