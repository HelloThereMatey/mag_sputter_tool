from __future__ import annotations

import os
import csv
import time
import bisect
from datetime import datetime
from typing import List

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QCheckBox, QLabel, QFileDialog
)

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas


class PlotterWindow(QMainWindow):
    """Live analog plotter for up to 4 channels.

    Usage: instantiate with a callable `read_fn()` that returns a list of 4 voltages
    (floats). The window will poll at `interval_ms` and update the plot.
    """

    def __init__(self, read_fn, parent=None, interval_ms: int = 500):
        super().__init__(parent)
        self.read_fn = read_fn
        self.interval_ms = interval_ms

        self.setWindowTitle("Analog Plotter")
        self._ensure_logs_dir()
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        central = QWidget(self)
        self.setCentralWidget(central)
        v = QVBoxLayout(central)

        # Controls
        ctrl = QHBoxLayout()
        self.checks: List[QCheckBox] = []
        for i in range(4):
            cb = QCheckBox(f"AI{i+1}")
            cb.setChecked(i < 2)
            ctrl.addWidget(cb)
            self.checks.append(cb)

        self.btn_record = QPushButton("Start Recording")
        self.btn_record.setCheckable(True)
        self.btn_record.clicked.connect(self._toggle_recording)
        ctrl.addWidget(self.btn_record)

        self.btn_save = QPushButton("Save Snapshot")
        self.btn_save.clicked.connect(self._save_snapshot)
        ctrl.addWidget(self.btn_save)

        ctrl.addStretch()
        v.addLayout(ctrl)

        # Matplotlib canvas
        self.fig = Figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("Analog Inputs (Volts)")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Voltage (V)")

        v.addWidget(self.canvas)

        # Internal state
        self.times: List[float] = []
        self.traces: List[List[float]] = [[ ] for _ in range(4)]
        self.start_time = time.time()
        # Rolling window in seconds (keep last N seconds of samples)
        self.max_window_s = 300.0
        # Recording
        self.recording = False
        self.csv_file = None
        self.csv_writer = None
        # Buffer pending rows to reduce I/O; flush every N ticks
        self._pending_rows = []
        self._write_batch_size = 25
        
        # Memory monitoring
        self._memory_check_interval = 10  # Check memory every 10 ticks (~2 seconds at 200ms interval)
        self._tick_count = 0
        try:
            import psutil
            self._psutil_available = True
        except ImportError:
            print("⚠️ WARNING: psutil not installed - memory monitoring disabled")
            print("   Install with: pip install psutil")
            self._psutil_available = False

    # Timer
        self.timer = QTimer(self)
        self.timer.setInterval(self.interval_ms)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _ensure_logs_dir(self) -> None:
        logs = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
        logs = os.path.abspath(logs)
        os.makedirs(logs, exist_ok=True)
        self.logs_dir = logs

    def _toggle_recording(self, checked: bool) -> None:
        if checked:
            # start
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            fname = os.path.join(self.logs_dir, f"plot_{stamp}.csv")
            self.csv_file = open(fname, 'w', newline='', encoding='utf-8')
            self.csv_writer = csv.writer(self.csv_file)
            header = ['t'] + [f'AI{i+1}' for i in range(4)]
            self.csv_writer.writerow(header)
            self.btn_record.setText('Stop Recording')
            # reset pending buffer and start
            self._pending_rows = []
            self.recording = True
        else:
            # stop
            # flush any pending rows before closing
            try:
                if self.csv_writer and self._pending_rows:
                    self.csv_writer.writerows(self._pending_rows)
                    try:
                        self.csv_file.flush()
                    except Exception:
                        pass
                    self._pending_rows = []
            except Exception:
                pass

            self.recording = False
            self.btn_record.setText('Start Recording')
            if self.csv_file:
                self.csv_file.close()
                self.csv_file = None
                self.csv_writer = None

    def _save_snapshot(self) -> None:
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        fname = os.path.join(self.logs_dir, f"snapshot_{stamp}.csv")
        with open(fname, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['t'] + [f'AI{i+1}' for i in range(4)])
            for i, t in enumerate(self.times):
                row = [t] + [self.traces[ch][i] if i < len(self.traces[ch]) else '' for ch in range(4)]
                w.writerow(row)

    def _flush_csv_buffer(self) -> None:
        """Safely flush pending rows with error handling."""
        try:
            if self.csv_writer and self._pending_rows:
                self.csv_writer.writerows(self._pending_rows)
                if self.csv_file:
                    self.csv_file.flush()
                self._pending_rows = []
        except IOError as e:
            print(f"🔴 CSV write failed: {e}")
            # Emergency dump to new file if primary write fails
            try:
                self._emergency_dump_csv()
            except Exception as dump_err:
                print(f"🔴 Emergency CSV dump also failed: {dump_err}")

    def _emergency_dump_csv(self) -> None:
        """Emergency dump of buffered CSV data to recovery file."""
        try:
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            fname = os.path.join(self.logs_dir, f"emergency_dump_{stamp}.csv")
            with open(fname, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['t'] + [f'AI{i+1}' for i in range(4)])
                w.writerows(self._pending_rows)
            print(f"💾 Emergency CSV dumped to {fname}")
            self._pending_rows = []
        except Exception as e:
            print(f"🔴 CRITICAL: Could not dump emergency CSV: {e}")

    def _check_memory_usage(self) -> None:
        """Monitor memory usage and trigger emergency reset if needed."""
        if not self._psutil_available:
            return
        
        try:
            import psutil
            import gc
            
            process = psutil.Process(os.getpid())
            mem_percent = process.memory_percent()
            
            if mem_percent > 80:
                print(f"🔴 CRITICAL: Memory usage at {mem_percent:.1f}% - emergency reset triggered")
                self._emergency_reset()
            elif mem_percent > 60:
                print(f"⚠️ WARNING: Memory usage at {mem_percent:.1f}% - forcing garbage collection")
                gc.collect()
        except Exception as e:
            print(f"🐛 Memory check failed: {e}")

    def _emergency_reset(self) -> None:
        """Emergency memory recovery - clear all data and buffers."""
        print("🚨 Emergency reset - clearing plots and buffers")
        try:
            # Stop recording if active
            if self.recording:
                self.recording = False
                self._flush_csv_buffer()
                self.btn_record.setText('Start Recording')
            
            # Clear all data
            self.times = []
            self.traces = [[] for _ in range(4)]
            self._pending_rows = []
            self.start_time = time.time()
            
            # Force garbage collection
            import gc
            gc.collect()
            
            print("✅ Emergency reset complete - data cleared")
        except Exception as e:
            print(f"🔴 Emergency reset failed: {e}")



    def _tick(self) -> None:
        """Poll read_fn and update plot."""
        try:
            values = self.read_fn()
        except Exception:
            values = [0.0, 0.0, 0.0, 0.0]

        t = time.time() - self.start_time
        self.times.append(t)
        for ch in range(4):
            self.traces[ch].append(float(values[ch]) if ch < len(values) else 0.0)

        # Recording to CSV (buffered): collect rows and write+flush every batch
        if self.recording and self.csv_writer:
            row = [t] + [self.traces[ch][-1] for ch in range(4)]
            self._pending_rows.append(row)
            
            # Bound buffer to prevent runaway memory (max ~10000 rows = 400KB)
            if len(self._pending_rows) > 10000:
                print("⚠️ WARNING: CSV buffer overflow (>10000 rows) - emergency dump and pause recording")
                self.recording = False
                self.btn_record.setText('Start Recording')
                self._flush_csv_buffer()
            elif len(self._pending_rows) >= self._write_batch_size:
                self._flush_csv_buffer()

        # Trim data older than the rolling window using binary search (O(log n) instead of O(n))
        try:
            cutoff = t - self.max_window_s
            if cutoff > 0 and len(self.times) > 1:
                # Use bisect for O(log n) search instead of O(n) linear search
                keep_idx = bisect.bisect_left(self.times, cutoff)
                
                if keep_idx > 0:
                    # Remove old data before cutoff
                    self.times = self.times[keep_idx:]
                    for ch in range(4):
                        self.traces[ch] = self.traces[ch][keep_idx:]
        except Exception:
            # Best-effort trimming; ignore on error
            pass

        # Update plot - clear entire figure to purge matplotlib render cache
        # (ax.clear() leaves internal caches that accumulate memory)
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        
        # Recreate axis labels and title
        self.ax.set_title('Analog Inputs (Volts)')
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Voltage (V)')
        
        # Plot only checked channels
        for ch in range(4):
            if self.checks[ch].isChecked():
                self.ax.plot(self.times, self.traces[ch], label=f'AI{ch+1}')
        self.ax.legend(loc='upper right')
        # Set x-axis to rolling window and autoscale Y only
        if self.times:
            xmax = self.times[-1]
            xmin = max(0.0, xmax - self.max_window_s)
            self.ax.set_xlim(xmin, xmax)
        self.ax.relim()
        self.ax.autoscale_view(scalex=False, scaley=True)
        self.canvas.draw()
        
        # Memory check (periodic, every N ticks to avoid overhead)
        self._tick_count += 1
        if self._tick_count >= self._memory_check_interval:
            self._tick_count = 0
            self._check_memory_usage()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        # ensure CSV file closed
        # flush any pending rows if recording before closing
        try:
            if self.csv_writer and self._pending_rows:
                self.csv_writer.writerows(self._pending_rows)
                try:
                    if self.csv_file:
                        self.csv_file.flush()
                except Exception:
                    pass
                self._pending_rows = []
        except Exception:
            pass

        if self.csv_file:
            self.csv_file.close()
        super().closeEvent(event)
