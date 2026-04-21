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

def find_process_by_name(name):
    try:
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] == name:
                return proc
    except Exception:
        pass
    return None

def monitor(pid, log_file, interval=0.5):
    try:
        vins_process = psutil.Process(pid)
    except psutil.NoSuchProcess:
        print(f"[Resource Monitor] VINS Process {pid} not found.")
        sys.exit(1)

    cam_process = None
    imu_process = None

    print(f"[Resource Monitor] Started monitoring PID {pid}")
    
    with open(log_file, 'w', newline='') as csvfile:
        # Basic fields
        fieldnames = ['timestamp', 'cpu_total']
        
        # Add dynamic core fields
        num_cores = psutil.cpu_count()
        for i in range(num_cores):
            fieldnames.append(f'cpu_{i}')
            
        fieldnames.extend(['vins_cpu', 'cam_cpu', 'imu_cpu', 'mem_mb', 'temp', 'freq_mhz'])
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        start_time = time.time()
        
        # Initial call to cpu_percent to initialize counters
        psutil.cpu_percent(percpu=True)
        vins_process.cpu_percent()
        
        while True:
            try:
                # Check if main process is still running
                if not vins_process.is_running() or vins_process.status() == psutil.STATUS_ZOMBIE:
                    break

                # Try to find accessory processes if not found yet
                if cam_process is None or not cam_process.is_running():
                    cam_process = find_process_by_name("camera_process")
                if imu_process is None or not imu_process.is_running():
                    imu_process = find_process_by_name("imu_process")

                current_time = time.time() - start_time
                
                # Utilization data
                cpu_total = psutil.cpu_percent(interval=None)
                per_cpu = psutil.cpu_percent(interval=None, percpu=True)
                
                vins_cpu = vins_process.cpu_percent()
                cam_cpu = cam_process.cpu_percent() if cam_process else 0.0
                imu_cpu = imu_process.cpu_percent() if imu_process else 0.0
                
                mem_mb = vins_process.memory_info().rss / (1024 * 1024)
                temp = get_temp()
                freq = get_cpu_freq()

                row = {
                    'timestamp': f"{current_time:.3f}",
                    'cpu_total': f"{cpu_total:.2f}",
                    'vins_cpu': f"{vins_cpu:.2f}",
                    'cam_cpu': f"{cam_cpu:.2f}",
                    'imu_cpu': f"{imu_cpu:.2f}",
                    'mem_mb': f"{mem_mb:.2f}",
                    'temp': f"{temp:.1f}",
                    'freq_mhz': f"{freq:.0f}"
                }
                
                # Add per-core data to row
                for i, val in enumerate(per_cpu):
                    if i < num_cores:
                        row[f'cpu_{i}'] = f"{val:.2f}"

                writer.writerow(row)
                csvfile.flush()
                
                time.sleep(interval)
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[Resource Monitor] Error: {e}")
                import traceback
                traceback.print_exc()
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
