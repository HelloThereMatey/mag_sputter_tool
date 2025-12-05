"""Logging configuration for sputter control system.

Sets up file-based logging with rotation to prevent terminal flooding.
Uses QueueHandler to ensure logging doesn't block the GUI thread.
Batches writes to disk every 60 seconds to minimize I/O overhead.
"""

import logging
import logging.handlers
from pathlib import Path
import sys
import queue
import threading
import time
from typing import List


class MemoryBufferedHandler(logging.Handler):
    """Custom handler that buffers log records in memory and flushes periodically.
    
    This reduces disk I/O by batching writes every flush_interval seconds.
    """
    
    def __init__(self, target_handler: logging.Handler, flush_interval: float = 60.0, buffer_size: int = 100):
        """Initialize the memory buffered handler.
        
        Args:
            target_handler: The actual file handler to write to
            flush_interval: Time in seconds between automatic flushes (default: 60s)
            buffer_size: Maximum number of records to buffer before forcing a flush (default: 100)
        """
        super().__init__()
        self.target_handler = target_handler
        self.flush_interval = flush_interval
        self.buffer_size = buffer_size
        self.buffer: List[logging.LogRecord] = []
        self.lock = threading.Lock()
        self.last_flush_time = time.time()
        
        # Start background flush thread
        self.stop_flush_thread = False
        self.flush_thread = threading.Thread(target=self._periodic_flush, daemon=True)
        self.flush_thread.start()
    
    def emit(self, record: logging.LogRecord):
        """Add record to buffer, flush if buffer is full or interval elapsed."""
        try:
            with self.lock:
                self.buffer.append(record)
                
                # Force flush if buffer is full or interval elapsed
                current_time = time.time()
                should_flush = (
                    len(self.buffer) >= self.buffer_size or
                    (current_time - self.last_flush_time) >= self.flush_interval
                )
                
                if should_flush:
                    self._flush_buffer()
        except Exception:
            self.handleError(record)
    
    def _flush_buffer(self):
        """Internal method to write buffered records to target handler."""
        if not self.buffer:
            return
            
        # Write all buffered records to target
        for record in self.buffer:
            self.target_handler.emit(record)
        
        # Flush target handler to ensure data is written to disk
        self.target_handler.flush()
        
        # Clear buffer and update flush time
        self.buffer.clear()
        self.last_flush_time = time.time()
    
    def _periodic_flush(self):
        """Background thread that flushes buffer periodically."""
        while not self.stop_flush_thread:
            time.sleep(self.flush_interval)
            with self.lock:
                if self.buffer:
                    self._flush_buffer()
    
    def flush(self):
        """Manually flush the buffer."""
        with self.lock:
            self._flush_buffer()
    
    def close(self):
        """Close handler and flush any remaining records."""
        self.stop_flush_thread = True
        if self.flush_thread.is_alive():
            self.flush_thread.join(timeout=2.0)
        
        with self.lock:
            self._flush_buffer()
        
        self.target_handler.close()
        super().close()


def setup_logging(log_dir: Path = None, log_level: int = logging.DEBUG) -> logging.Logger:
    """Configure logging for the application.
    
    Args:
        log_dir: Directory to store log files (default: ~/.sputter_control/logs/)
        log_level: Logging level (default: DEBUG)
        
    Returns:
        Root logger instance
    """
    try:
        if log_dir is None:
            # Use platform-appropriate cache directory
            if sys.platform == "win32":
                cache_dir = Path.home() / ".sputter_control"
            else:
                cache_dir = Path.home() / ".cache" / "sputter_control"
            
            log_dir = cache_dir / "logs"
        
        # Create log directory if it doesn't exist
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Log file paths
        main_log = log_dir / "sputter_control.log"
        arduino_log = log_dir / "arduino_comm.log"
        gas_log = log_dir / "gas_control.log"
        
        # Root logger configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Remove any existing handlers
        root_logger.handlers.clear()
        
        # Console handler - only warnings and above to avoid terminal flooding
        # This goes directly to stdout (not through queue for important messages)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)
        console_formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # Main log file handler with rotation (10MB max, keep 5 files)
        main_file_handler = logging.handlers.RotatingFileHandler(
            main_log,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        main_file_handler.setLevel(logging.INFO)
        main_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        main_file_handler.setFormatter(main_formatter)
        
        # Wrap main handler in memory buffer (flush every 60 seconds)
        buffered_main_handler = MemoryBufferedHandler(
            main_file_handler, 
            flush_interval=60.0,  # Flush every 60 seconds
            buffer_size=100  # Or when buffer reaches 100 records
        )
        buffered_main_handler.setLevel(logging.INFO)
        root_logger.addHandler(buffered_main_handler)
        
        # Create a queue and queue handler for non-blocking logging
        # This prevents file I/O from blocking the GUI thread
        log_queue = queue.Queue(-1)  # Unlimited queue size
        queue_handler = logging.handlers.QueueHandler(log_queue)
        
        # Arduino communication logger - detailed debug logs
        arduino_logger = logging.getLogger('arduino')
        arduino_file_handler = logging.handlers.RotatingFileHandler(
            arduino_log,
            maxBytes=10*1024*1024,
            backupCount=3,
            encoding='utf-8'
        )
        arduino_file_handler.setLevel(logging.DEBUG)
        arduino_formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        arduino_file_handler.setFormatter(arduino_formatter)
        
        # Wrap Arduino handler in memory buffer
        buffered_arduino_handler = MemoryBufferedHandler(
            arduino_file_handler,
            flush_interval=60.0,
            buffer_size=100
        )
        buffered_arduino_handler.setLevel(logging.DEBUG)
        
        # Use queue handler to avoid blocking
        arduino_queue_handler = logging.handlers.QueueHandler(log_queue)
        arduino_logger.addHandler(arduino_queue_handler)
        arduino_logger.setLevel(logging.DEBUG)
        arduino_logger.propagate = False  # Don't propagate to root logger
        
        # Gas control logger - detailed debug logs
        gas_logger = logging.getLogger('gas_control')
        gas_file_handler = logging.handlers.RotatingFileHandler(
            gas_log,
            maxBytes=10*1024*1024,
            backupCount=3,
            encoding='utf-8'
        )
        gas_file_handler.setLevel(logging.DEBUG)
        gas_formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        gas_file_handler.setFormatter(gas_formatter)
        
        # Wrap Gas handler in memory buffer
        buffered_gas_handler = MemoryBufferedHandler(
            gas_file_handler,
            flush_interval=60.0,
            buffer_size=100
        )
        buffered_gas_handler.setLevel(logging.DEBUG)
        
        # Use queue handler to avoid blocking
        gas_queue_handler = logging.handlers.QueueHandler(log_queue)
        gas_logger.addHandler(gas_queue_handler)
        gas_logger.setLevel(logging.DEBUG)
        gas_logger.propagate = False  # Don't propagate to root logger
        
        # Create and start the queue listener in a background thread
        # This handles the actual file writing asynchronously
        # Note: Queue listener writes to buffered handlers, which batch writes to disk
        queue_listener = logging.handlers.QueueListener(
            log_queue,
            buffered_main_handler,
            buffered_arduino_handler,
            buffered_gas_handler,
            respect_handler_level=True
        )
        queue_listener.start()
        
        # Store listener reference to prevent garbage collection
        root_logger._queue_listener = queue_listener
        
        # Log startup message
        root_logger.info("=" * 80)
        root_logger.info("Sputter Control System - Logging Started")
        root_logger.info(f"Log directory: {log_dir}")
        root_logger.info("=" * 80)
        
        return root_logger
    
    except Exception as e:
        # If logging setup fails, create a minimal console-only logger
        print(f"ERROR: Failed to set up file logging: {e}", file=sys.stderr)
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.WARNING)
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.WARNING)
        console.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        root_logger.addHandler(console)
        return root_logger
def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module.
    
    Args:
        name: Logger name (e.g., 'arduino', 'gas_control', 'safety')
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)
