#!/usr/bin/env python3
"""
Advanced timing diagnostics to identify the source of slow MFC communication.

This script tests various hypotheses about why Python async is 140x slower 
than the CLI tool (1400ms vs 10ms).
"""

import asyncio
import sys
import time
import subprocess
import tempfile
import os
from alicat import FlowController


def time_cli_command(serial_port='/dev/ttyUSB0', unit='A'):
    """Time the actual CLI command for comparison."""
    
    print(f"\n⚡ CLI Command Timing")
    print("=" * 30)
    
    try:
        # Time the CLI command
        start = time.perf_counter()
        result = subprocess.run(['alicat', serial_port, '--unit', unit], 
                              capture_output=True, text=True, timeout=10)
        end = time.perf_counter()
        
        cli_time = (end - start) * 1000
        
        if result.returncode == 0:
            print(f"CLI time:     {cli_time:.1f} ms")
            print(f"CLI output:   {result.stdout.strip()[:100]}...")
            return cli_time
        else:
            print(f"CLI failed:   {result.stderr}")
            return None
            
    except Exception as e:
        print(f"CLI error:    {e}")
        return None


async def test_with_custom_timeout_and_baud(serial_port='/dev/ttyUSB0', unit='A'):
    """Test different timeout and baud rate combinations."""
    
    print(f"\n🔧 Custom Settings Test")
    print("=" * 40)
    
    # Test combinations
    configs = [
        {'timeout': 0.05},  # Very short timeout
        {'timeout': 0.1},   # Short timeout  
        {'timeout': 0.5},   # Medium timeout
        {'timeout': 1.0},   # Default timeout
    ]
    
    for config in configs:
        timeout = config.get('timeout', 1.0)
        
        print(f"\nTesting timeout={timeout}s:")
        
        times = []
        for i in range(3):
            start = time.perf_counter()
            try:
                # Try different FlowController initialization approaches
                fc = FlowController(address=serial_port, unit=unit, timeout=timeout)
                
                async with fc:
                    result = await fc.get()
                    end = time.perf_counter()
                    
                    response_time = (end - start) * 1000
                    times.append(response_time)
                    print(f"  Attempt {i+1}: {response_time:6.1f}ms - Flow: {result.get('mass_flow', 'N/A')}")
                    
            except Exception as e:
                end = time.perf_counter()
                response_time = (end - start) * 1000
                print(f"  Attempt {i+1}: {response_time:6.1f}ms - ERROR: {str(e)[:40]}...")
        
        if times:
            avg_time = sum(times) / len(times)
            print(f"  Average:     {avg_time:6.1f}ms")


async def test_sync_vs_async_overhead():
    """Test if asyncio itself is adding overhead."""
    
    print(f"\n🔄 Async vs Sync Overhead Test")
    print("=" * 40)
    
    # Time just the asyncio event loop overhead
    async def minimal_async():
        await asyncio.sleep(0.001)  # 1ms sleep
        return "done"
    
    # Test async overhead
    start = time.perf_counter()
    result = await minimal_async()
    end = time.perf_counter()
    async_overhead = (end - start) * 1000
    
    print(f"Minimal async overhead: {async_overhead:.3f}ms")
    
    # Test multiple async calls
    start = time.perf_counter()
    for i in range(10):
        await minimal_async()
    end = time.perf_counter()
    multi_async_overhead = (end - start) * 1000
    
    print(f"10x async calls:        {multi_async_overhead:.3f}ms ({multi_async_overhead/10:.3f}ms each)")


async def test_raw_serial_communication(serial_port='/dev/ttyUSB0', unit='A'):
    """Try to access raw serial communication if possible."""
    
    print(f"\n🔌 Raw Serial Communication Test")
    print("=" * 45)
    
    try:
        # Create FlowController and try to access internals
        fc = FlowController(address=serial_port, unit=unit, timeout=0.5)
        
        print("FlowController created, examining internals...")
        
        # Check what attributes are available
        attrs = [attr for attr in dir(fc) if not attr.startswith('_')]
        print(f"Public attributes: {attrs[:10]}...")  # Show first 10
        
        # Try to access the connection
        async with fc:
            print("Connected, checking internal state...")
            
            # See if we can access the serial connection
            if hasattr(fc, 'connection') or hasattr(fc, '_connection'):
                conn = getattr(fc, 'connection', None) or getattr(fc, '_connection', None)
                print(f"Connection object: {type(conn)}")
                
            # Time a simple get operation with detailed logging
            print("Timing detailed get() operation...")
            start = time.perf_counter()
            result = await fc.get()
            end = time.perf_counter()
            
            response_time = (end - start) * 1000
            print(f"Detailed get() time: {response_time:.1f}ms")
            print(f"Result: {result}")
            
    except Exception as e:
        print(f"Raw serial test error: {e}")
        import traceback
        traceback.print_exc()


async def comprehensive_speed_test(serial_port='/dev/ttyUSB0', unit='A'):
    """Run comprehensive speed comparison."""
    
    print(f"\n🚀 Comprehensive Speed Test")
    print("=" * 50)
    
    # 1. CLI timing
    cli_time = time_cli_command(serial_port, unit)
    
    # 2. Async overhead test
    await test_sync_vs_async_overhead()
    
    # 3. Multiple Python attempts with different approaches
    print(f"\n📊 Python AsyncIO Attempts:")
    print("-" * 30)
    
    approaches = [
        ("Standard async with", "async with FlowController(...) as fc: await fc.get()"),
        ("Manual connection", "fc = FlowController(...); await fc.__aenter__(); await fc.get(); await fc.__aexit__(...)"),
        ("Ultra-short timeout", "async with FlowController(..., timeout=0.01) as fc: await fc.get()"),
    ]
    
    for approach_name, description in approaches:
        print(f"\n{approach_name}:")
        times = []
        
        for i in range(3):
            start = time.perf_counter()
            try:
                if approach_name == "Standard async with":
                    async with FlowController(address=serial_port, unit=unit) as fc:
                        result = await fc.get()
                elif approach_name == "Manual connection":
                    fc = FlowController(address=serial_port, unit=unit)
                    await fc.__aenter__()
                    result = await fc.get()
                    await fc.__aexit__(None, None, None)
                elif approach_name == "Ultra-short timeout":
                    async with FlowController(address=serial_port, unit=unit, timeout=0.01) as fc:
                        result = await fc.get()
                
                end = time.perf_counter()
                response_time = (end - start) * 1000
                times.append(response_time)
                print(f"  Attempt {i+1}: {response_time:6.1f}ms")
                
            except Exception as e:
                end = time.perf_counter()
                response_time = (end - start) * 1000
                print(f"  Attempt {i+1}: {response_time:6.1f}ms - ERROR: {str(e)[:30]}...")
        
        if times:
            avg_time = sum(times) / len(times)
            print(f"  Average:   {avg_time:6.1f}ms")
            
            if cli_time:
                slowdown = avg_time / cli_time
                print(f"  Slowdown:  {slowdown:.1f}x vs CLI")


async def investigate_alicat_internals(serial_port='/dev/ttyUSB0', unit='A'):
    """Try to understand what's happening inside the alicat library."""
    
    print(f"\n🔍 Alicat Library Investigation")
    print("=" * 45)
    
    try:
        # Import and examine the FlowController class
        from alicat.driver import FlowController as FC
        
        print(f"FlowController class: {FC}")
        print(f"FlowController module: {FC.__module__}")
        
        # Check if there are any class-level timeouts or delays
        fc_attrs = [attr for attr in dir(FC) if not attr.startswith('__')]
        print(f"FlowController methods: {fc_attrs}")
        
        # Create instance and examine
        fc = FC(address=serial_port, unit=unit, timeout=0.1)
        
        print(f"Instance created with timeout: {getattr(fc, 'timeout', 'unknown')}")
        
        # Time the connection establishment separately
        print("\nTiming connection phases:")
        
        connect_start = time.perf_counter()
        await fc.__aenter__()
        connect_end = time.perf_counter()
        connect_time = (connect_end - connect_start) * 1000
        print(f"Connection time: {connect_time:.1f}ms")
        
        # Time the actual communication
        comm_start = time.perf_counter()
        result = await fc.get()
        comm_end = time.perf_counter()
        comm_time = (comm_end - comm_start) * 1000
        print(f"Communication time: {comm_time:.1f}ms")
        
        # Time the disconnection
        disconnect_start = time.perf_counter()
        await fc.__aexit__(None, None, None)
        disconnect_end = time.perf_counter()
        disconnect_time = (disconnect_end - disconnect_start) * 1000
        print(f"Disconnection time: {disconnect_time:.1f}ms")
        
        total_time = connect_time + comm_time + disconnect_time
        print(f"Total time: {total_time:.1f}ms")
        
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"Investigation error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Advanced MFC Timing Diagnostics')
    parser.add_argument('--port', default='/dev/ttyUSB0', 
                       help='Serial port (default: /dev/ttyUSB0)')
    parser.add_argument('--unit', default='A', type=str, 
                       help='Unit ID to test (default: A)')
    parser.add_argument('--comprehensive', action='store_true',
                       help='Run comprehensive speed test')
    parser.add_argument('--internals', action='store_true',
                       help='Investigate alicat library internals')
    parser.add_argument('--settings', action='store_true',
                       help='Test different timeout/baud settings')
    parser.add_argument('--raw', action='store_true',
                       help='Test raw serial communication')
    
    args = parser.parse_args()
    
    try:
        if args.comprehensive:
            asyncio.run(comprehensive_speed_test(args.port, args.unit))
        elif args.internals:
            asyncio.run(investigate_alicat_internals(args.port, args.unit))
        elif args.settings:
            asyncio.run(test_with_custom_timeout_and_baud(args.port, args.unit))
        elif args.raw:
            asyncio.run(test_raw_serial_communication(args.port, args.unit))
        else:
            # Default: comprehensive test
            print("Running comprehensive speed diagnostics...")
            print("Use specific flags for targeted tests")
            asyncio.run(comprehensive_speed_test(args.port, args.unit))
        
        print(f"\n💡 For direct comparison, run:")
        print(f"   time alicat {args.port} --unit {args.unit}")
        
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()