#!/usr/bin/env python3

"""
Comprehensive test suite runner for countdown join window feature.

This script runs all test suites to verify the countdown join window feature:
1. Basic countdown join functionality
2. Late join prevention 
3. Functional/synthetic tests
4. Integration with existing per-player ABC system
"""

import asyncio
import subprocess
import sys
import time

def run_test_script(script_name):
    """Run a test script and return success status."""
    print(f"\n{'='*60}")
    print(f"🧪 Running {script_name}")
    print('='*60)
    
    start_time = time.time()
    
    try:
        result = subprocess.run([sys.executable, script_name], 
                              capture_output=False, 
                              text=True, 
                              cwd='.')
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ {script_name} PASSED ({duration:.1f}s)")
            return True
        else:
            print(f"❌ {script_name} FAILED ({duration:.1f}s)")
            return False
            
    except Exception as e:
        duration = time.time() - start_time
        print(f"💥 {script_name} CRASHED: {e} ({duration:.1f}s)")
        return False

def main():
    """Run all countdown join window tests."""
    print("🚀 Comprehensive Test Suite: Countdown Join Window Feature")
    print("=" * 80)
    
    # List of all test scripts to run
    test_scripts = [
        "test_countdown_join.py",           # Basic join during countdown
        "test_late_join_prevention.py",    # Late join prevention
        "test_functional_countdown_join.py", # Synthetic functional tests
        "test_per_player_abc.py"           # Verify existing functionality still works
    ]
    
    results = []
    total_start_time = time.time()
    
    # Run each test script
    for script in test_scripts:
        success = run_test_script(script)
        results.append((script, success))
    
    total_duration = time.time() - total_start_time
    
    # Print summary
    print(f"\n{'='*80}")
    print("📊 TEST SUMMARY")
    print('='*80)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for script, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}  {script}")
    
    print(f"\n🏁 Results: {passed}/{total} test suites passed")
    print(f"⏱️  Total time: {total_duration:.1f}s")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("🔒 Countdown join window feature is working correctly!")
        print("\nFeature Summary:")
        print("  ✓ Players can join during countdown animation ('?' phase)")
        print("  ✓ Players cannot join after countdown window closes") 
        print("  ✓ Late joiners get blank cubes instead of letters")
        print("  ✓ Independent ABC completion still works for individual players")
        print("  ✓ Integration with existing per-player systems maintained")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test suite(s) failed!")
        print("🔧 Please review failed tests and fix issues.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)