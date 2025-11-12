#!/usr/bin/env python3
"""
Debug timing issues with Alicat MFC communications.

This script breaks down the timing of each step to identify bottlenecks
and compare with the CLI performance.
"""

import asyncio
import sys
import time
from alicat import FlowController


async def detailed_timing_analysis(unit_id='A', serial_port='/dev/ttyUSB0'):
    """Break down timing of each step in the communication process."""
    
    print(f"\n🔬 Detailed Timing Analysis for unit {unit_id}")
    print(f"   Port: {serial_port}")
    print("=" * 60)
    
    total_start = time.perf_counter()
    
    try:
        # Step 1: Constructor timing
        constructor_start = time.perf_counter()
        fc = FlowController(address=serial_port, unit=unit_id, timeout=1.0)
        constructor_end = time.perf_counter()
        constructor_time = (constructor_end - constructor_start) * 1000
        print(f"1. Constructor:       {constructor_time:8.1f} ms")
        
        # Step 2: Connection/initialization timing
        connect_start = time.perf_counter()
        await fc.__aenter__()  # Manual context manager entry
        connect_end = time.perf_counter()
        connect_time = (connect_end - connect_start) * 1000
        print(f"2. Connection init:   {connect_time:8.1f} ms")
        
        # Step 3: First communication timing
        first_read_start = time.perf_counter()
        result1 = await fc.get()
        first_read_end = time.perf_counter()
        first_read_time = (first_read_end - first_read_start) * 1000
        print(f"3. First read:        {first_read_time:8.1f} ms")
        
        # Step 4: Second communication timing (should be faster)
        second_read_start = time.perf_counter()
        result2 = await fc.get()
        second_read_end = time.perf_counter()
        second_read_time = (second_read_end - second_read_start) * 1000
        print(f"4. Second read:       {second_read_time:8.1f} ms")
        
        # Step 5: Third communication timing
        third_read_start = time.perf_counter()
        result3 = await fc.get()
        third_read_end = time.perf_counter()
        third_read_time = (third_read_end - third_read_start) * 1000
        print(f"5. Third read:        {third_read_time:8.1f} ms")
        
        # Step 6: Disconnection timing
        disconnect_start = time.perf_counter()
        await fc.__aexit__(None, None, None)  # Manual context manager exit
        disconnect_end = time.perf_counter()
        disconnect_time = (disconnect_end - disconnect_start) * 1000
        print(f"6. Disconnection:     {disconnect_time:8.1f} ms")
        
        total_end = time.perf_counter()
        total_time = (total_end - total_start) * 1000
        
        print("-" * 60)
        print(f"Total time:           {total_time:8.1f} ms")
        print(f"Pure read time avg:   {(first_read_time + second_read_time + third_read_time)/3:8.1f} ms")
        print(f"Overhead time:        {total_time - (first_read_time + second_read_time + third_read_time):8.1f} ms")
        
        print(f"\n📊 Data received:")
        print(f"   Reading 1: {result1}")
        print(f"   Reading 2: {result2}")
        print(f"   Reading 3: {result3}")
        
        return {
            'constructor_ms': constructor_time,
            'connection_ms': connect_time,
            'first_read_ms': first_read_time,
            'second_read_ms': second_read_time,
            'third_read_ms': third_read_time,
            'disconnect_ms': disconnect_time,
            'total_ms': total_time,
            'overhead_ms': total_time - (first_read_time + second_read_time + third_read_time)
        }
        
    except Exception as e:
        total_end = time.perf_counter()
        total_time = (total_end - total_start) * 1000
        print(f"❌ Error after {total_time:.1f}ms: {e}")
        return None


async def test_different_timeouts(unit_id='A', serial_port='/dev/ttyUSB0'):
    """Test different timeout values to see impact on performance."""
    
    print(f"\n⏱️  Timeout Testing for unit {unit_id}")
    print("=" * 50)
    
    timeouts = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
    
    for timeout in timeouts:
        print(f"\nTesting timeout: {timeout}s")
        print("-" * 30)
        
        times = []
        for i in range(3):
            start = time.perf_counter()
            try:
                async with FlowController(address=serial_port, unit=unit_id, timeout=timeout) as fc:
                    result = await fc.get()
                    end = time.perf_counter()
                    response_time = (end - start) * 1000
                    times.append(response_time)
                    print(f"  Reading {i+1}: {response_time:6.1f}ms - Success")
            except Exception as e:
                end = time.perf_counter()
                response_time = (end - start) * 1000
                print(f"  Reading {i+1}: {response_time:6.1f}ms - Error: {str(e)[:30]}...")
        
        if times:
            avg_time = sum(times) / len(times)
            print(f"  Average:   {avg_time:6.1f}ms")


async def minimal_cli_reproduction(unit_id='A', serial_port='/dev/ttyUSB0'):
    """Try to reproduce the exact CLI behavior with minimal code."""
    
    print(f"\n🎯 Minimal CLI Reproduction for unit {unit_id}")
    print("=" * 50)
    
    # This is almost exactly what the CLI does
    start_time = time.perf_counter()
    
    try:
        async with FlowController(address=serial_port, unit=unit_id) as flow_controller:
            state = await flow_controller.get()
            end_time = time.perf_counter()
            
            response_time = (end_time - start_time) * 1000
            print(f"Response time: {response_time:.1f} ms")
            print(f"Data: {state}")
            
            return response_time
            
    except Exception as e:
        end_time = time.perf_counter()
        response_time = (end_time - start_time) * 1000
        print(f"Error after {response_time:.1f}ms: {e}")
        return None


async def serial_port_investigation(serial_port='/dev/ttyUSB0'):
    """Investigate serial port settings and behavior."""
    
    print(f"\n🔌 Serial Port Investigation")
    print("=" * 40)
    
    try:
        # Try to access the underlying serial connection details
        print(f"Port: {serial_port}")
        
        # Test with minimal timeout first
        start = time.perf_counter()
        async with FlowController(address=serial_port, unit='A', timeout=0.1) as fc:
            # Access internal serial connection if possible
            if hasattr(fc, '_serial'):
                print(f"Serial object: {fc._serial}")
                if hasattr(fc._serial, 'timeout'):
                    print(f"Serial timeout: {fc._serial.timeout}")
                if hasattr(fc._serial, 'baudrate'):
                    print(f"Baudrate: {fc._serial.baudrate}")
            
            result = await fc.get()
            end = time.perf_counter()
            
            print(f"Minimal timeout test: {(end-start)*1000:.1f}ms")
            print(f"Result: {result}")
            
    except Exception as e:
        print(f"Investigation error: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Debug MFC Timing Issues')
    parser.add_argument('--port', default='/dev/ttyUSB0', 
                       help='Serial port (default: /dev/ttyUSB0)')
    parser.add_argument('--unit', default='A', type=str, 
                       help='Unit ID to test (default: A)')
    parser.add_argument('--all', action='store_true',
                       help='Run all diagnostic tests')
    parser.add_argument('--timeouts', action='store_true',
                       help='Test different timeout values')
    parser.add_argument('--detailed', action='store_true',
                       help='Run detailed timing analysis')
    parser.add_argument('--minimal', action='store_true',
                       help='Run minimal CLI reproduction')
    parser.add_argument('--serial', action='store_true',
                       help='Investigate serial port settings')
    
    args = parser.parse_args()
    
    try:
        if args.all:
            # Run all tests
            print("🚀 Running Complete Diagnostic Suite")
            print("=" * 60)
            
            asyncio.run(serial_port_investigation(args.port))
            asyncio.run(minimal_cli_reproduction(args.unit, args.port))
            asyncio.run(detailed_timing_analysis(args.unit, args.port))
            asyncio.run(test_different_timeouts(args.unit, args.port))
            
        elif args.timeouts:
            asyncio.run(test_different_timeouts(args.unit, args.port))
        elif args.detailed:
            asyncio.run(detailed_timing_analysis(args.unit, args.port))
        elif args.minimal:
            asyncio.run(minimal_cli_reproduction(args.unit, args.port))
        elif args.serial:
            asyncio.run(serial_port_investigation(args.port))
        else:
            # Default: run minimal test
            print("Running minimal CLI reproduction test...")
            print("Use --all for complete diagnostics")
            asyncio.run(minimal_cli_reproduction(args.unit, args.port))
        
        print(f"\n💡 For comparison, run: time alicat {args.port} --unit {args.unit}")
        
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()