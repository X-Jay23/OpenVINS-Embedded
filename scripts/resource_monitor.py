#!/usr/bin/env python3
import psutil
import time
import argparse
import csv
import sys
import os

def get_cpu_freq():
    try:
        freq = psutil.cpu_freq()
        return freq.current if freq else 0.0
    except Exception:
        return 0.0

def get_temp():
    """
    Get the system temperature, prioritizing CPU/Soc sensors.
    """
    try:
        # 1. Try psutil sensors_temperatures()
        temps = psutil.sensors_temperatures()
        if temps:
            # Priority keys for CPU/SoC sensors across different platforms
            priority_keys = ['coretemp', 'soc_thermal', 'cpu_thermal', 'cpu-thermal', 'k10temp']
            for pk in priority_keys:
                if pk in temps:
                    entries = temps[pk]
                    # For Intel 'coretemp', 'Package id 0' is the best representative
                    for entry in entries:
                        if entry.label and 'package' in entry.label.lower():
                            return entry.current
                    # Fallback to first entry of priority key
                    if entries:
                        return entries[0].current
            
            # If no priority keys found, return max of all valid sensors (excluding static ones like acpitz if others exist)
            all_valid = []
            for name, entries in temps.items():
                if name == 'acpitz' and len(temps) > 1:
                    continue # Skip acpitz if we have better candidates
                for entry in entries:
                    if entry.current > 0:
                        all_valid.append(entry.current)
            
            if all_valid:
                return max(all_valid)
            elif 'acpitz' in temps and temps['acpitz']:
                return temps['acpitz'][0].current

    except Exception:
        pass

    # 2. Hard fallback to /sys/class/thermal (useful for some embedded ARM platforms)
    try:
        if os.path.exists('/sys/class/thermal/'):
            zones = []
            for d in os.listdir('/sys/class/thermal/'):
                if d.startswith('thermal_zone'):
                    try:
                        base_path = os.path.join('/sys/class/thermal/', d)
                        with open(os.path.join(base_path, 'type'), 'r') as f:
                            ztype = f.read().strip().lower()
                        with open(os.path.join(base_path, 'temp'), 'r') as f:
                            ztemp = float(f.read().strip()) / 1000.0
                        zones.append((ztype, ztemp))
                    except (IOError, ValueError):
                        continue
            
            if zones:
                # Prefer zones explicitly labeled cpu or soc
                for ztype, ztemp in zones:
                    if 'cpu' in ztype or 'soc' in ztype:
                        return ztemp
                # Otherwise return max
                return max([z[1] for z in zones])
    except Exception:
        pass

    return 0.0

def monitor(pid, log_file, interval=0.5):
    try:
        process = psutil.Process(pid)
    except psutil.NoSuchProcess:
        print(f"[Resource Monitor] Process {pid} not found.")
        sys.exit(1)

    print(f"[Resource Monitor] Started monitoring PID {pid}")
    
    with open(log_file, 'w', newline='') as csvfile:
        fieldnames = ['timestamp', 'cpu_percent', 'mem_mb', 'temp', 'freq_mhz']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        start_time = time.time()
        
        while True:
            try:
                # Check if process is still running
                if not process.is_running() or process.status() == psutil.STATUS_ZOMBIE:
                    break

                current_time = time.time() - start_time
                cpu_percent = psutil.cpu_percent(interval=None) # Non-blocking whole system CPU
                mem_info = process.memory_info()
                mem_mb = mem_info.rss / (1024 * 1024)
                temp = get_temp()
                freq = get_cpu_freq()

                writer.writerow({
                    'timestamp': f"{current_time:.3f}",
                    'cpu_percent': f"{cpu_percent:.2f}",
                    'mem_mb': f"{mem_mb:.2f}",
                    'temp': f"{temp:.1f}",
                    'freq_mhz': f"{freq:.0f}"
                })
                csvfile.flush()
                
                time.sleep(interval)
                
            except psutil.NoSuchProcess:
                break
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[Resource Monitor] Error: {e}")
                break

    print(f"[Resource Monitor] Stopped monitoring PID {pid}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor process resource usage.")
    parser.add_argument("pid", type=int, help="Process ID to monitor")
    parser.add_argument("log_file", type=str, help="Output CSV file path")
    parser.add_argument("--interval", type=float, default=0.5, help="Sampling interval in seconds")
    
    args = parser.parse_args()
    
    # Ensure log directory exists
    os.makedirs(os.path.dirname(args.log_file), exist_ok=True)
    
    monitor(args.pid, args.log_file, args.interval)
