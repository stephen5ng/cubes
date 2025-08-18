#!/usr/bin/env python3
"""
Diagnose system impact on random_letters.sh timing.
"""

import asyncio
import time
import subprocess
import threading
import os
import psutil
import statistics

class SystemImpactTest:
    def __init__(self):
        self.cpu_samples = []
        self.memory_samples = []
        self.timing_samples = []
        self.running = True
        
    def monitor_system_resources(self):
        """Monitor CPU and memory usage"""
        while self.running:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            self.cpu_samples.append((time.time(), cpu_percent))
            self.memory_samples.append((time.time(), memory.percent))
            
            time.sleep(0.5)
            
    async def test_sleep_accuracy(self, target_sleep=0.25, iterations=100):
        """Test how accurate Python's sleep is under load"""
        print(f"Testing sleep accuracy ({target_sleep}s target, {iterations} iterations)...")
        
        actual_sleeps = []
        
        for i in range(iterations):
            start_time = time.time()
            await asyncio.sleep(target_sleep)
            actual_sleep = time.time() - start_time
            actual_sleeps.append(actual_sleep)
            
            if i % 10 == 0:
                print(f"  Iteration {i:3d}: {actual_sleep*1000:.1f}ms (target: {target_sleep*1000}ms)")
                
        return actual_sleeps
        
    def get_high_cpu_processes(self, threshold=5.0):
        """Get processes using more than threshold% CPU"""
        high_cpu = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
            try:
                if proc.info['cpu_percent'] and proc.info['cpu_percent'] > threshold:
                    high_cpu.append((proc.info['pid'], proc.info['name'], proc.info['cpu_percent']))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
        return sorted(high_cpu, key=lambda x: x[2], reverse=True)
        
    async def run_comprehensive_test(self):
        """Run comprehensive system impact test"""
        print("System Impact Analysis for random_letters.sh Latency")
        print("=" * 60)
        
        # Start system monitoring
        monitor_thread = threading.Thread(target=self.monitor_system_resources)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # Test 1: Baseline sleep accuracy
        print("\n1. Baseline Sleep Accuracy Test")
        baseline_sleeps = await self.test_sleep_accuracy(0.25, 50)
        
        # Test 2: Check current system load
        print("\n2. Current System Load")
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        load_avg = os.getloadavg()
        
        print(f"  CPU Usage: {cpu_percent:.1f}%")
        print(f"  Memory Usage: {memory.percent:.1f}% ({memory.used // (1024**3):.1f}GB / {memory.total // (1024**3):.1f}GB)")
        print(f"  Load Average: {load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}")
        
        # Test 3: Identify high CPU processes
        print("\n3. High CPU Processes")
        high_cpu = self.get_high_cpu_processes(5.0)
        if high_cpu:
            print("  Processes using >5% CPU:")
            for pid, name, cpu in high_cpu[:10]:
                print(f"    PID {pid:6d}: {name:30s} {cpu:5.1f}%")
        else:
            print("  No processes using >5% CPU")
            
        # Test 4: Test under artificial load
        print("\n4. Testing Under Artificial CPU Load")
        print("  Creating CPU load for 10 seconds...")
        
        def cpu_burner():
            """Create CPU load"""
            end_time = time.time() + 10
            while time.time() < end_time:
                pass  # Busy loop
                
        # Start CPU load in background
        cpu_thread = threading.Thread(target=cpu_burner)
        cpu_thread.start()
        
        # Test sleep accuracy under load
        loaded_sleeps = await self.test_sleep_accuracy(0.25, 40)
        
        cpu_thread.join()
        
        # Test 5: Recovery test
        print("\n5. Recovery Test (after load)")
        await asyncio.sleep(2)  # Let system recover
        recovery_sleeps = await self.test_sleep_accuracy(0.25, 20)
        
        self.running = False
        monitor_thread.join(timeout=1)
        
        # Analysis
        self.analyze_results(baseline_sleeps, loaded_sleeps, recovery_sleeps)
        
    def analyze_results(self, baseline_sleeps, loaded_sleeps, recovery_sleeps):
        """Analyze test results"""
        print("\n" + "="*60)
        print("ANALYSIS RESULTS")
        print("="*60)
        
        def analyze_sleep_set(sleeps, name, target=0.25):
            if not sleeps:
                return
                
            sleeps_ms = [s * 1000 for s in sleeps]
            target_ms = target * 1000
            
            print(f"\n{name} Sleep Analysis:")
            print(f"  Target: {target_ms:.1f}ms")
            print(f"  Mean: {statistics.mean(sleeps_ms):.2f}ms")
            print(f"  Median: {statistics.median(sleeps_ms):.2f}ms")
            print(f"  Min: {min(sleeps_ms):.2f}ms")
            print(f"  Max: {max(sleeps_ms):.2f}ms")
            print(f"  Std Dev: {statistics.stdev(sleeps_ms):.2f}ms")
            
            # Count problematic sleeps
            overruns = [s for s in sleeps_ms if s > target_ms * 1.5]  # >50% over target
            severe_overruns = [s for s in sleeps_ms if s > target_ms * 2.0]  # >100% over target
            
            if overruns:
                print(f"  Overruns (>50% over): {len(overruns)} ({len(overruns)/len(sleeps)*100:.1f}%)")
            if severe_overruns:
                print(f"  Severe overruns (>100% over): {len(severe_overruns)} ({len(severe_overruns)/len(sleeps)*100:.1f}%)")
                print(f"  Worst overrun: {max(severe_overruns):.2f}ms")
                
        analyze_sleep_set(baseline_sleeps, "Baseline")
        analyze_sleep_set(loaded_sleeps, "Under CPU Load")
        analyze_sleep_set(recovery_sleeps, "Recovery")
        
        # System monitoring results
        if self.cpu_samples:
            cpu_values = [sample[1] for sample in self.cpu_samples]
            print(f"\nSystem Monitoring During Test:")
            print(f"  CPU Usage - Mean: {statistics.mean(cpu_values):.1f}%, Max: {max(cpu_values):.1f}%")
            
        # Recommendations
        print(f"\nRECOMMENDations:")
        
        baseline_mean = statistics.mean([s * 1000 for s in baseline_sleeps]) if baseline_sleeps else 0
        loaded_mean = statistics.mean([s * 1000 for s in loaded_sleeps]) if loaded_sleeps else 0
        
        if loaded_mean > baseline_mean * 1.5:
            print("  ❌ CONFIRMED: High CPU load significantly impacts timing accuracy")
            print("  ❌ This is likely causing the random_letters.sh latency issues")
            print()
            print("  SOLUTIONS:")
            print("  1. Close unnecessary applications (especially Chrome tabs)")
            print("  2. Use Activity Monitor to identify CPU-heavy processes")
            print("  3. Consider using 'nice' command to prioritize cube processes")
            print("  4. Check for background processes (Time Machine, Spotlight indexing)")
            print("  5. Consider upgrading hardware if consistently overloaded")
        else:
            print("  ✅ CPU load does not significantly impact timing")
            print("  ✅ The latency issue is likely elsewhere (network, MQTT, ESP32)")
        
        # Check specific thresholds
        if baseline_sleeps:
            baseline_overruns = len([s for s in baseline_sleeps if s > 0.25 * 1.5])
            if baseline_overruns > len(baseline_sleeps) * 0.1:  # >10% overruns
                print("  ⚠️  Even baseline timing is problematic - system may be overloaded")

async def main():
    test = SystemImpactTest()
    
    import signal
    def signal_handler(sig, frame):
        test.running = False
        
    signal.signal(signal.SIGINT, signal_handler)
    
    await test.run_comprehensive_test()

if __name__ == "__main__":
    asyncio.run(main())