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
            fig, axs = plt.subplots(3, 1, figsize=(10, 12), sharex=True)
            
            axs[0].plot(df['timestamp'], df['cpu_percent'], color='b', label='CPU Usage (%)')
            axs[0].set_ylabel('CPU (%)')
            axs[0].legend()
            axs[0].grid(True)
            axs[0].set_title('System CPU Utilization')
            
            axs[1].plot(df['timestamp'], df['mem_mb'], color='g', label='VINS Mem (MB)')
            axs[1].set_ylabel('Memory (MB)')
            axs[1].legend()
            axs[1].grid(True)
            axs[1].set_title('VINS Process Memory (RSS)')
            
            axs[2].plot(df['timestamp'], df['temp'], color='r', label='Temp (°C)')
            axs[2].set_ylabel('Temperature (°C)', color='r')
            axs[2].tick_params(axis='y', labelcolor='r')
            
            ax2_freq = axs[2].twinx()
            ax2_freq.plot(df['timestamp'], df['freq_mhz'], color='orange', linestyle='--', label='Freq (MHz)')
            ax2_freq.set_ylabel('Frequency (MHz)', color='orange')
            ax2_freq.tick_params(axis='y', labelcolor='orange')
            
            lines, labels = axs[2].get_legend_handles_labels()
            lines2, labels2 = ax2_freq.get_legend_handles_labels()
            ax2_freq.legend(lines + lines2, labels + labels2, loc=0)
            axs[2].grid(True)
            axs[2].set_xlabel('Time (s)')
            axs[2].set_title('CPU Temperature and Frequency')
            
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
