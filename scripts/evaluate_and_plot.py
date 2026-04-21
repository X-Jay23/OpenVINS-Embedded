#!/usr/bin/env python3
import os
import argparse
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from scipy.interpolate import interp1d
from mpl_toolkits.mplot3d import Axes3D

def align_trajectories(model, data, align_scale=False):
    """
    Implementation of the Umeyama algorithm to align individual trajectories.
    model: estimated trajectory (N, 3)
    data: ground truth trajectory (N, 3)
    """
    if model.shape[0] < 2:
        return model
        
    model_zerocentered = model - np.mean(model, axis=0)
    data_zerocentered = data - np.mean(data, axis=0)

    # Covariance matrix
    K = np.dot(data_zerocentered.T, model_zerocentered)
    U, S, Vt = np.linalg.svd(K)
    V = Vt.T
    
    # Rotation
    R = np.dot(U, V.T)
    if np.linalg.det(R) < 0:
        S_det = np.eye(3)
        S_det[2, 2] = -1
        R = np.dot(np.dot(U, S_det), V.T)
    
    # Scale (usually 1.0 for VIO)
    scale = 1.0
    if align_scale:
        var_model = np.var(model_zerocentered)
        scale = np.trace(np.diag(S)) / (var_model * model.shape[0])
        
    # Translation
    t = np.mean(data, axis=0) - scale * np.dot(R, np.mean(model, axis=0))
    
    # Aligned trajectory
    model_aligned = scale * np.dot(model, R.T) + t
    return model_aligned

def compute_metrics(traj_file, gt_file):
    """ Load, sync, and align trajectories. """
    print("[Evaluation] Synchronizing and Alinging trajectories...")
    
    if not os.path.exists(traj_file) or not os.path.exists(gt_file):
        print(f"Error: Required files missing. Traj: {os.path.exists(traj_file)}, GT: {os.path.exists(gt_file)}")
        return None

    try:
        # Load Predict (Estimate) - OpenVINS format
        try:
            df_est = pd.read_csv(traj_file, sep=' ', header=None)
        except:
            df_est = pd.read_csv(traj_file, sep='\t', header=None)
        
        ts_est = df_est.iloc[:, 0].values.astype(float)
        pos_est = df_est.iloc[:, 1:4].values

        # Load Ground Truth - EuRoC format
        df_gt = pd.read_csv(gt_file, comment='#', header=None)
        ts_gt = df_gt.iloc[:, 0].values.astype(float) * 1e-9
        pos_gt = df_gt.iloc[:, 1:4].values

        # Time Alignment: find common time interval
        t_start = max(ts_gt[0], ts_est[0])
        t_end = min(ts_gt[-1], ts_est[-1])
        
        if t_start >= t_end:
            print("Error: No overlapping time interval found.")
            return None

        # Filter and Interpolate
        mask_est = (ts_est >= t_start) & (ts_est <= t_end)
        ts_est_sync = ts_est[mask_est]
        pos_est_sync = pos_est[mask_est]
        
        f_x = interp1d(ts_gt, pos_gt[:, 0], kind='linear', fill_value='extrapolate')
        f_y = interp1d(ts_gt, pos_gt[:, 1], kind='linear', fill_value='extrapolate')
        f_z = interp1d(ts_gt, pos_gt[:, 2], kind='linear', fill_value='extrapolate')
        
        pos_gt_interp = np.zeros_like(pos_est_sync)
        pos_gt_interp[:, 0] = f_x(ts_est_sync)
        pos_gt_interp[:, 1] = f_y(ts_est_sync)
        pos_gt_interp[:, 2] = f_z(ts_est_sync)

        # Spatial Alignment (Umeyama)
        pos_est_aligned = align_trajectories(pos_est_sync, pos_gt_interp)
        
        # Calculate Errors
        errors = np.linalg.norm(pos_est_aligned - pos_gt_interp, axis=1)
        rmse = np.sqrt(np.mean(errors**2))
        
        return {
            'rmse': rmse,
            'ts': ts_est_sync,
            'est_aligned': pos_est_aligned,
            'gt_interp': pos_gt_interp,
            'errors': errors,
            'gt_full': pos_gt
        }

    except Exception as e:
        print(f"Failed to compute metrics: {e}")
        return None

def plot_report(log_dir, metrics):
    resource_file = os.path.join(log_dir, "resource.csv")
    pdf_path = os.path.join(log_dir, "performance_report.pdf")
    
    print(f"[Evaluation] Generating professional PDF report at: {pdf_path}")
    
    with PdfPages(pdf_path) as pdf:
        # Page 1: Resource Utilization
        if os.path.exists(resource_file):
            df = pd.read_csv(resource_file)
            core_cols = sorted([c for c in df.columns if c.startswith('cpu_') and c != 'cpu_total' and c != 'cpu_percent'])
            cpu_main_col = 'cpu_total' if 'cpu_total' in df.columns else 'cpu_percent'
            
            num_plots = 4 if core_cols else 3
            fig, axs = plt.subplots(num_plots, 1, figsize=(12, 4 * num_plots), sharex=True)
            
            # Subplot 0: System/Process CPU
            axs[0].plot(df['timestamp'], df[cpu_main_col], color='black', linewidth=1.5, label='Total System CPU')
            for comp, color in [('vins_cpu', 'royalblue'), ('cam_cpu', 'forestgreen'), ('imu_cpu', 'orange')]:
                if comp in df.columns:
                    axs[0].plot(df['timestamp'], df[comp], label=comp.replace('_cpu', '').upper(), alpha=0.7)
            axs[0].set_ylabel('CPU (%)')
            axs[0].legend(loc='upper right', fontsize='small', ncol=2)
            axs[0].grid(True, alpha=0.3)
            axs[0].set_title('System & Process CPU Utilization', fontweight='bold')

            # Subplot 1: Per-Core (if available)
            curr = 1
            if core_cols:
                for col in core_cols:
                    axs[curr].plot(df['timestamp'], df[col], label=col, alpha=0.6)
                axs[curr].set_ylabel('CPU (%)')
                axs[curr].legend(loc='upper right', fontsize='x-small', ncol=4)
                axs[curr].grid(True, alpha=0.3)
                axs[curr].set_title('Per-Core Load Distribution', fontweight='bold')
                curr += 1

            # Subplot: Memory
            axs[curr].plot(df['timestamp'], df['mem_mb'], color='darkgreen', label='VINS RSS Memory')
            axs[curr].set_ylabel('Memory (MB)')
            axs[curr].grid(True, alpha=0.3)
            axs[curr].set_title('Process Memory Usage', fontweight='bold')
            curr += 1
            
            # Subplot: Temp & Freq
            axs[curr].plot(df['timestamp'], df['temp'], color='crimson', label='Temp (°C)')
            axs[curr].set_ylabel('Temperature (°C)', color='crimson')
            ax2 = axs[curr].twinx()
            ax2.plot(df['timestamp'], df['freq_mhz'], color='orange', linestyle='--', label='Freq (MHz)')
            ax2.set_ylabel('Frequency (MHz)', color='orange')
            axs[curr].grid(True, alpha=0.3)
            axs[curr].set_title('Hardware Thermal & Frequency State', fontweight='bold')
            
            plt.tight_layout()
            pdf.savefig(fig)
            plt.close()

        # Page 2: Advanced Trajectory Overview
        if metrics:
            fig = plt.figure(figsize=(16, 12))
            
            # 1. 3D Trajectory
            ax3d = fig.add_subplot(2, 2, 1, projection='3d')
            ax3d.plot(metrics['gt_full'][:, 0], metrics['gt_full'][:, 1], metrics['gt_full'][:, 2], 
                     color='gray', linestyle=':', label='Ground Truth (Full)', alpha=0.4)
            ax3d.plot(metrics['est_aligned'][:, 0], metrics['est_aligned'][:, 1], metrics['est_aligned'][:, 2], 
                     color='royalblue', label='VINS Estimate (Aligned)', linewidth=2)
            ax3d.set_title('3D Trajectory Comparison', fontweight='bold')
            ax3d.legend(fontsize='small')
            
            # 2. XY Plane
            ax_xy = fig.add_subplot(2, 2, 2)
            ax_xy.plot(metrics['gt_interp'][:, 0], metrics['gt_interp'][:, 1], color='crimson', linestyle='--', label='Ground Truth', alpha=0.6)
            ax_xy.plot(metrics['est_aligned'][:, 0], metrics['est_aligned'][:, 1], color='royalblue', label='VINS Estimate', linewidth=2)
            ax_xy.set_title('XY Plane Projection (Top-down)', fontweight='bold')
            ax_xy.set_xlabel('X [m]')
            ax_xy.set_ylabel('Y [m]')
            ax_xy.axis('equal')
            ax_xy.grid(True, alpha=0.3)
            ax_xy.legend(fontsize='small')

            # 3. XZ Plane
            ax_xz = fig.add_subplot(2, 2, 3)
            ax_xz.plot(metrics['gt_interp'][:, 0], metrics['gt_interp'][:, 2], color='crimson', linestyle='--', label='Ground Truth', alpha=0.6)
            ax_xz.plot(metrics['est_aligned'][:, 0], metrics['est_aligned'][:, 2], color='royalblue', label='VINS Estimate', linewidth=2)
            ax_xz.set_title('XZ Plane Projection (Side-view)', fontweight='bold')
            ax_xz.set_xlabel('X [m]')
            ax_xz.set_ylabel('Z [m]')
            ax_xz.axis('equal')
            ax_xz.grid(True, alpha=0.3)
            ax_xz.legend(fontsize='small')

            # 4. ATE Error Curve
            ax_err = fig.add_subplot(2, 2, 4)
            time_axis = metrics['ts'] - metrics['ts'][0]
            ax_err.fill_between(time_axis, metrics['errors'], color='royalblue', alpha=0.2)
            ax_err.plot(time_axis, metrics['errors'], color='royalblue', linewidth=1)
            ax_err.set_title('Absolute Trajectory Error (ATE) Over Time', fontweight='bold')
            ax_err.set_xlabel('Time [s]')
            ax_err.set_ylabel('Error [m]')
            ax_err.grid(True, alpha=0.3)

            plt.suptitle(f"Trajectory Accuracy Metrics (ATE RMSE: {metrics['rmse']:.4f} m)", fontsize=16, fontweight='bold')
            plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            pdf.savefig(fig)
            plt.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Evaluate VINS metrics.")
    parser.add_argument("log_dir", help="Directory containing resource.csv and trajectory.txt")
    parser.add_argument("gt_file", help="Path to ground truth CSV")
    args = parser.parse_args()
    
    traj_path = os.path.join(args.log_dir, "trajectory.txt")
    metrics = compute_metrics(traj_path, args.gt_file)
    plot_report(args.log_dir, metrics)
