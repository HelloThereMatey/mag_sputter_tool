# Logging System for Sputter Control

## Overview

The sputter control system uses Python's built-in logging framework with **asynchronous file-based output** to prevent terminal flooding and ensure the GUI remains responsive during intensive logging operations.

### Key Features:
- **Non-blocking logging**: Uses `QueueHandler` and `QueueListener` to write logs asynchronously
- **Batched disk writes**: Buffers up to 100 log records in memory, writes every 60 seconds
- **GUI thread protection**: File I/O happens in a background thread, preventing GUI freezes
- **Automatic rotation**: Logs rotate at 10MB to prevent disk space issues
- **Separate log files**: Arduino, gas control, and main logs kept separate for easier debugging

## Log Files Location

Logs are stored in a platform-appropriate cache directory:
- **Windows**: `C:\Users\<username>\.sputter_control\logs\`
- **Linux/RPi**: `~/.cache/sputter_control/logs/`

## Log Files

### 1. `sputter_control.log`
- Main application log
- General system events, errors, and warnings
- Rotation: 10MB max, keeps 5 backup files
- Level: INFO and above

### 2. `arduino_comm.log`
- Detailed Arduino communication logs
- Command/response tracking
- Queue statistics (every 5 seconds)
- Serial I/O timing
- Rotation: 10MB max, keeps 3 backup files
- Level: DEBUG (all details)

### 3. `gas_control.log`
- Gas flow controller operations
- MFC CLI command execution
- Subprocess timing and errors
- Command processing stats (every 5 seconds)
- Rotation: 10MB max, keeps 3 backup files
- Level: DEBUG (all details)

## Console Output

The terminal now only shows:
- **WARNING** level and above (errors, critical issues)
- Important user-facing messages (procedure status, safety alerts)
- This prevents terminal flooding while keeping critical info visible

## Debug Information Captured

### Arduino Communication (`arduino_comm.log`):
- Every command sent with UUID
- Command execution time
- Response content (truncated if long)
- Queue sizes every 5 seconds (when active)
- Serial write/read timing
- Timeout details with elapsed time
- Thread heartbeat (every 10 minutes)

### Gas Flow Controller (`gas_control.log`):
- CLI command execution with full arguments
- Subprocess timing
- Command processing stats every 5 seconds
- Timeout and error details
- Retry attempts

## Performance Impact

- **Near-zero GUI impact**: Logging uses asynchronous queue-based writing with memory buffering
- **Batched disk I/O**: Writes to disk every 60 seconds (or when buffer reaches 100 records)
- **Background thread**: All file I/O happens in a dedicated logging thread
- **5-second stats interval**: Reduced from 1-second to minimize overhead
- **Conditional logging**: Only logs slow operations for analog/digital reads
- **No GUI blocking**: QueueHandler ensures the GUI thread never waits for disk I/O

### How It Works:
1. Logger calls (e.g., `logger.debug()`) put records in a memory queue - nearly instant
2. A background `QueueListener` thread processes the queue
3. Records are buffered in memory by `MemoryBufferedHandler` (up to 100 records or 60 seconds)
4. File writing happens asynchronously in batches every 60 seconds
5. Console output (warnings/errors) still goes directly to terminal for visibility

### Memory Buffering:
- Each log file buffers up to **100 records** or **60 seconds** of logs before writing
- This reduces disk I/O by ~98% (60 writes/hour instead of 3600 writes/hour at 1 Hz)
- Records are never lost - buffer is flushed on program exit
- Force flush occurs immediately if buffer reaches 100 records

## Viewing Logs

### Real-time monitoring:
```bash
# Linux/RPi
tail -f ~/.cache/sputter_control/logs/arduino_comm.log
tail -f ~/.cache/sputter_control/logs/gas_control.log

# Windows PowerShell
Get-Content -Path "$env:USERPROFILE\.sputter_control\logs\arduino_comm.log" -Wait -Tail 50
```

### Searching for issues:
```bash
# Linux/RPi
grep -i "timeout" ~/.cache/sputter_control/logs/arduino_comm.log
grep -i "error" ~/.cache/sputter_control/logs/*.log

# Windows PowerShell
Select-String -Path "$env:USERPROFILE\.sputter_control\logs\*.log" -Pattern "timeout" -CaseSensitive:$false
```

## Configuration

To modify logging settings, edit `logging_config.py`:
- Change log levels (DEBUG, INFO, WARNING, ERROR)
- Adjust rotation size/backup count
- Add new specialized loggers
- Modify console output level

## Troubleshooting

### If logs aren't being created:
1. Check directory permissions for `~/.sputter_control/logs/`
### To increase verbosity:
Edit `logging_config.py` and change:
```python
console_handler.setLevel(logging.DEBUG)  # Show everything in terminal
```

### To adjust flush interval:
Edit `logging_config.py` and modify the `MemoryBufferedHandler` parameters:
```python
buffered_handler = MemoryBufferedHandler(
    file_handler,
    flush_interval=30.0,  # Flush every 30 seconds instead of 60
    buffer_size=50        # Or when buffer reaches 50 records instead of 100
)
```ogs auto-rotate at 10MB
- Only 3-5 backup files kept per log
- Max total disk usage: ~150MB for all logs

### To increase verbosity:
Edit `logging_config.py` and change:
```python
## Integration with Existing Code

The logging system is transparent to existing code:
- `print()` statements for user-facing messages still work
- Critical errors still appear in terminal
- Debug logs captured to file automatically
- Logs buffered in memory and written every 60 seconds
- No changes needed to calling code

**Note**: If the program crashes, up to 60 seconds of logs may be in the buffer.
However, Python's logging system automatically flushes on abnormal termination.control.log.1` → `sputter_control.log.2` → ... → `sputter_control.log.5`
- Oldest backup files are automatically deleted
- No manual cleanup needed

## Integration with Existing Code

The logging system is transparent to existing code:
- `print()` statements for user-facing messages still work
- Critical errors still appear in terminal
- Debug logs captured to file automatically
- No changes needed to calling code
