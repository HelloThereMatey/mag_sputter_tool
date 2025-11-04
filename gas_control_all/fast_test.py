#!/usr/bin/env python3
"""
Fast Alicat MFC test script using CLI-optimized connection pattern.

This script mimics the alicat CLI's efficient connection management
to achieve <10ms response times like the command line tool.
"""

import asyncio
import sys
import time
import statistics
from alicat import FlowController


async def cli_style_reading(unit_id='A', serial_port='/dev/ttyUSB0'):
    """Get a single reading using CLI-style connection management.
    
    This mimics exactly what the alicat CLI does for maximum speed.
    """
    start_time = time.perf_counter()
    try:
        # Use context manager like CLI for efficient connection handling
        async with FlowController(address=serial_port, unit=unit_id) as flow_controller:
            state = await flow_controller.get()
            end_time = time.perf_counter()
            
            response_time = (end_time - start_time) * 1000  # Convert to milliseconds
            return {
                'success': True,
                'response_time_ms': response_time,
                'data': state
            }
            
    except Exception as e:
        end_time = time.perf_counter()
        response_time = (end_time - start_time) * 1000
        return {
            'success': False,
            'response_time_ms': response_time,
            'error': str(e)
        }


async def fast_connectivity_scan(serial_port='/dev/ttyUSB0'):
    """Fast connectivity scan using CLI-style connections."""
    
    print("🚀 Fast Connectivity Scan (CLI-Style)")
    print("-" * 50)
    
    units_found = []
    
    for unit_id in ['A', 'B', 'C', 'D', 'E']:
        print(f"Testing unit {unit_id}... ", end="", flush=True)
        
        result = await cli_style_reading(unit_id, serial_port)
        
        if result['success']:
            data = result['data']
            print(f"✅ FOUND ({result['response_time_ms']:.1f}ms) - {data.get('gas', 'Unknown gas')}")
            print(f"    Flow: {data.get('mass_flow', 'N/A'):>8.3f} "
                  f"Temp: {data.get('temperature', 'N/A'):>6.2f}°C "
                  f"Pressure: {data.get('pressure', 'N/A'):>6.2f}")
            units_found.append(unit_id)
        else:
            print(f"❌ No response ({result['response_time_ms']:.1f}ms)")
    
    print(f"\nFound {len(units_found)} MFC(s) at unit IDs: {units_found}")
    return units_found


async def fast_benchmark(unit_id='A', serial_port='/dev/ttyUSB0', num_readings=10):
    """Fast benchmark using CLI-style connections for each reading."""
    
    print(f"\n🏃‍♂️ Fast Benchmark for unit {unit_id}")
    print(f"   Port: {serial_port}")
    print(f"   Readings: {num_readings}")
    print(f"   Method: CLI-style (fresh connection per reading)")
    print("-" * 60)
    
    response_times = []
    successful_readings = 0
    
    for i in range(num_readings):
        print(f"Reading {i+1:2d}/{num_readings}: ", end="", flush=True)
        
        result = await cli_style_reading(unit_id, serial_port)
        
        if result['success']:
            response_times.append(result['response_time_ms'])
            successful_readings += 1
            data = result['data']
            print(f"{result['response_time_ms']:6.1f}ms - Flow: {data.get('mass_flow', 'N/A'):>8.3f}")
        else:
            print(f"{result['response_time_ms']:6.1f}ms - ❌ ERROR: {result['error'][:30]}...")
        
        # Small delay between readings (optional)
        await asyncio.sleep(0.05)
    
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


async def benchmark_all_units_fast(serial_port='/dev/ttyUSB0', num_readings=10):
    """Fast benchmark all units using CLI-style connections."""
    
    print("🚀 CLI-Style Fast MFC Benchmark")
    print("=" * 70)
    print(f"Serial Port: {serial_port}")
    print(f"Readings per unit: {num_readings}")
    print(f"Connection method: Fresh connection per reading (like CLI)")
    print()
    
    # First, quick scan to find units
    units_found = await fast_connectivity_scan(serial_port)
    
    if not units_found:
        print("\n❌ No units found. Cannot proceed with benchmark.")
        return []
    
    # Benchmark each found unit
    all_stats = []
    for unit_id in units_found:
        stats = await fast_benchmark(unit_id, serial_port, num_readings)
        if stats:
            all_stats.append(stats)
    
    # Summary comparison
    if all_stats:
        print("\n" + "=" * 70)
        print("📊 FAST BENCHMARK SUMMARY")
        print("=" * 70)
        print(f"{'Unit':<4} {'Success%':<8} {'Avg(ms)':<8} {'Min(ms)':<8} {'Max(ms)':<8} {'StdDev':<8}")
        print("-" * 70)
        
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
            
        print(f"\n💡 Compare with CLI command: alicat {serial_port} --unit A")
    
    return all_stats


async def compare_connection_methods(unit_id='A', serial_port='/dev/ttyUSB0', num_readings=5):
    """Compare different connection methods to understand performance differences."""
    
    print(f"\n🔬 Connection Method Comparison for unit {unit_id}")
    print("=" * 60)
    
    # Method 1: CLI-style (fresh connection each time)
    print("\n📋 Method 1: CLI-style (fresh connection per reading)")
    cli_times = []
    for i in range(num_readings):
        result = await cli_style_reading(unit_id, serial_port)
        if result['success']:
            cli_times.append(result['response_time_ms'])
            print(f"  Reading {i+1}: {result['response_time_ms']:.1f}ms")
    
    # Method 2: Persistent connection (like your original script)
    print(f"\n📋 Method 2: Persistent connection ({num_readings} readings)")
    persistent_times = []
    try:
        fc = FlowController(address=serial_port, unit=unit_id, timeout=2)
        
        for i in range(num_readings):
            start_time = time.perf_counter()
            result = await fc.get()
            end_time = time.perf_counter()
            response_time = (end_time - start_time) * 1000
            persistent_times.append(response_time)
            print(f"  Reading {i+1}: {response_time:.1f}ms")
            await asyncio.sleep(0.05)
        
        await fc.close()
        
    except Exception as e:
        print(f"  ❌ Error with persistent connection: {e}")
    
    # Compare results
    if cli_times and persistent_times:
        print(f"\n📊 Comparison Results:")
        print(f"   CLI-style average:    {statistics.mean(cli_times):.1f} ms")
        print(f"   Persistent average:   {statistics.mean(persistent_times):.1f} ms")
        print(f"   Speed improvement:    {statistics.mean(persistent_times)/statistics.mean(cli_times):.1f}x faster with CLI method")


def print_usage():
    """Print usage instructions."""
    print("\n" + "=" * 60)
    print("FAST TEST USAGE OPTIONS:")
    print("=" * 60)
    print("1. Fast scan:         python fast_test.py")
    print("2. Fast benchmark:    python fast_test.py --benchmark")
    print("3. Single unit:       python fast_test.py --unit A")
    print("4. Compare methods:   python fast_test.py --compare")
    print("5. Custom port:       python fast_test.py --port COM3")
    print()
    print("Examples:")
    print("  python fast_test.py --benchmark --readings 20")
    print("  python fast_test.py --compare --unit B")
    print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Fast MFC Test (CLI-Style)')
    parser.add_argument('--port', default='/dev/ttyUSB0', 
                       help='Serial port (default: /dev/ttyUSB0)')
    parser.add_argument('--unit', type=str, 
                       help='Test specific unit ID (A, B, C, D, E)')
    parser.add_argument('--benchmark', action='store_true',
                       help='Run fast benchmark on found units')
    parser.add_argument('--compare', action='store_true',
                       help='Compare connection methods')
    parser.add_argument('--readings', type=int, default=10,
                       help='Number of readings for benchmark (default: 10)')
    
    args = parser.parse_args()
    
    # Adjust port for Windows if needed
    if sys.platform.startswith('win') and args.port.startswith('/dev/'):
        print("⚠️  Detected Windows but Unix-style port path.")
        print("   Consider using --port COM3, COM4, etc.")
        print()
    
    try:
        if args.compare:
            unit = args.unit or 'A'
            print(f"Comparing connection methods for unit {unit}")
            asyncio.run(compare_connection_methods(unit, args.port, args.readings))
        elif args.unit:
            # Test specific unit
            print(f"Fast testing unit {args.unit} on {args.port}")
            asyncio.run(fast_benchmark(args.unit, args.port, args.readings))
        elif args.benchmark:
            # Run fast benchmark
            asyncio.run(benchmark_all_units_fast(args.port, args.readings))
        else:
            # Fast connectivity scan
            asyncio.run(fast_connectivity_scan(args.port))
        
        print_usage()
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()