#!/usr/bin/env python3
import os
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import tempfile

def compute_ate_rpe_numpy(traj_file, gt_file):
    """
    Compute ATE and RPE using basic numpy instead of full evo pipeline.
    This acts as a robust fallback.
    """
    print("[Evaluation] Calculating ATE/RPE using numpy...")
    
    # Load VINS Trajectory (TUM format: sec x y z qx qy qz qw)
    try:
        traj_data = np.loadtxt(traj_file)
        if traj_data.ndim == 1:
            traj_data = traj_data.reshape(1, -1)
        traj_ts = traj_data[:, 0]
        traj_pos = traj_data[:, 1:4]
    except Exception as e:
        print(f"Error loading trajectory file: {e}")
        return None, None
        
    # Load EuroC Ground Truth (ns_timestamp p_RS_R_x p_RS_R_y p_RS_R_z ...)
    try:
        gt_df = pd.read_csv(gt_file, comment='#')
        # EuroC GT columns: #timestamp,p_RS_R_x[m],p_RS_R_y[m],p_RS_R_z[m], q_RS_w[],...
        gt_ts = gt_df.iloc[:, 0].values / 1e9 # ns to s
        gt_pos = gt_df.iloc[:, 1:4].values
    except Exception as e:
        print(f"Error loading ground truth file: {e}")
        return None, None

    # Temporal Alignment (Nearest neighbor mapping)
    aligned_traj_pos = []
    aligned_gt_pos = []
    
    # Very simple alignment: For each estimated timestamp, find the closest GT timestamp
    for i, t in enumerate(traj_ts):
        idx = np.abs(gt_ts - t).argmin()
        if np.abs(gt_ts[idx] - t) < 0.05: # Only associate if within 50ms
            aligned_traj_pos.append(traj_pos[i])
            aligned_gt_pos.append(gt_pos[idx])
            
    if not aligned_traj_pos:
        print("Failed to align trajectories.")
        return None, None
        
    aligned_traj_pos = np.array(aligned_traj_pos)
    aligned_gt_pos = np.array(aligned_gt_pos)
    
    # 1. ATE (Absolute Trajectory Error) - RMSE of translation
    # Note: Proper ATE requires Sim3/SE3 alignment. Here we assume identity alignment 
    # since VINS should be in the same gravity-aligned Vicon frame as Euroc GT initially.
    ate_errors = np.linalg.norm(aligned_traj_pos - aligned_gt_pos, axis=1)
    ate_rmse = np.sqrt(np.mean(ate_errors**2))
    
    # 2. RPE (Relative Pose Error) - Translation drift per 1 second step
    rpe_errors = []
    fps_approx = 20 # Assuming 20fps for Euroc
    step = fps_approx * 1 # 1 second steps
    
    if len(aligned_traj_pos) > step:
        for i in range(len(aligned_traj_pos) - step):
            # Delta pos in estimate
            delta_est = aligned_traj_pos[i+step] - aligned_traj_pos[i]
            # Delta pos in GT
            delta_gt = aligned_gt_pos[i+step] - aligned_gt_pos[i]
            
            # Error in delta
            rpe_err = np.linalg.norm(delta_est - delta_gt)
            rpe_errors.append(rpe_err)
            
    rpe_rmse = np.sqrt(np.mean(np.array(rpe_errors)**2)) if rpe_errors else 0.0
    
    return ate_rmse, rpe_rmse


def plot_metrics(log_dir, traj_file, gt_file, ate, rpe):
    resource_file = os.path.join(log_dir, "resource.csv")
    pdf_path = os.path.join(log_dir, "performance_report.pdf")
    
    print(f"[Evaluation] Generating PDF report at: {pdf_path}")
    
    with PdfPages(pdf_path) as pdf:
        # Plot 1: Resources Monitor
        if os.path.exists(resource_file):
            df = pd.read_csv(resource_file)
            
            # Detect available columns
            core_cols = sorted([c for c in df.columns if c.startswith('cpu_') and c != 'cpu_total' and c != 'cpu_percent'])
            cpu_main_col = 'cpu_total' if 'cpu_total' in df.columns else 'cpu_percent'
            
            num_plots = 4 if core_cols else 3
            fig, axs = plt.subplots(num_plots, 1, figsize=(10, 4 * num_plots), sharex=True)
            
            # Subplot 0: System and Process CPU
            axs[0].plot(df['timestamp'], df[cpu_main_col], color='black', linewidth=1.5, label='Total System CPU')
            if 'vins_cpu' in df.columns:
                axs[0].plot(df['timestamp'], df['vins_cpu'], label='VINS Process', alpha=0.8)
            if 'cam_cpu' in df.columns:
                axs[0].plot(df['timestamp'], df['cam_cpu'], label='Camera Process', alpha=0.8)
            if 'imu_cpu' in df.columns:
                axs[0].plot(df['timestamp'], df['imu_cpu'], label='IMU Process', alpha=0.8)
            
            axs[0].set_ylabel('CPU (%)')
            axs[0].legend(loc='upper right', fontsize='small', ncol=2)
            axs[0].grid(True, alpha=0.3)
            axs[0].set_title('CPU Utilization (System & Components)')

            # Subplot 1: Per-Core CPU (if available)
            plot_idx = 1
            if core_cols:
                for col in core_cols:
                    axs[plot_idx].plot(df['timestamp'], df[col], label=col, alpha=0.7)
                axs[plot_idx].set_ylabel('CPU (%)')
                axs[plot_idx].legend(loc='upper right', fontsize='x-small', ncol=min(4, len(core_cols)))
                axs[plot_idx].grid(True, alpha=0.3)
                axs[plot_idx].set_title('Per-Core CPU Utilization')
                plot_idx += 1

            # Subplot: Memory
            axs[plot_idx].plot(df['timestamp'], df['mem_mb'], color='g', label='VINS Mem (MB)')
            axs[plot_idx].set_ylabel('Memory (MB)')
            axs[plot_idx].legend(loc='upper right')
            axs[plot_idx].grid(True, alpha=0.3)
            axs[plot_idx].set_title('VINS Process Memory (RSS)')
            plot_idx += 1
            
            # Subplot: Temp and Freq
            axs[plot_idx].plot(df['timestamp'], df['temp'], color='r', label='Temp (°C)')
            axs[plot_idx].set_ylabel('Temperature (°C)', color='r')
            axs[plot_idx].tick_params(axis='y', labelcolor='r')
            
            ax2_freq = axs[plot_idx].twinx()
            ax2_freq.plot(df['timestamp'], df['freq_mhz'], color='orange', linestyle='--', label='Freq (MHz)')
            ax2_freq.set_ylabel('Frequency (MHz)', color='orange')
            ax2_freq.tick_params(axis='y', labelcolor='orange')
            
            lines, labels = axs[plot_idx].get_legend_handles_labels()
            lines2, labels2 = ax2_freq.get_legend_handles_labels()
            ax2_freq.legend(lines + lines2, labels + labels2, loc='upper right', fontsize='small')
            axs[plot_idx].grid(True, alpha=0.3)
            axs[plot_idx].set_xlabel('Time (s)')
            axs[plot_idx].set_title('CPU Temperature and Frequency')
            
            plt.tight_layout()
            pdf.savefig(fig)
            plt.close()
            
        # Plot 2: Trajectory Error Summary
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.1, 0.8, "Performance Metrics Summary", fontsize=16, fontweight='bold')
        if ate is not None and rpe is not None:
            ax.text(0.1, 0.6, f"Absolute Trajectory Error (ATE RMSE): {ate:.4f} m", fontsize=12)
            ax.text(0.1, 0.5, f"Relative Pose Error (1s RPE RMSE): {rpe:.4f} m", fontsize=12)
        else:
            ax.text(0.1, 0.6, "Failed to calculate trajectory errors.", fontsize=12)
        ax.axis('off')
        pdf.savefig(fig)
        plt.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Evaluate VINS metrics.")
    parser.add_argument("log_dir", help="Directory containing resource.csv and trajectory.txt")
    parser.add_argument("gt_file", help="Path to ground truth CSV")
    args = parser.parse_args()
    
    traj_path = os.path.join(args.log_dir, "trajectory.txt")
    ate, rpe = compute_ate_rpe_numpy(traj_path, args.gt_file)
    plot_metrics(args.log_dir, traj_path, args.gt_file, ate, rpe)
