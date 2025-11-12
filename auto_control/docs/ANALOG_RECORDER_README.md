# Analog Input Recorder

## Overview

The Analog Input Recorder provides a lightweight alternative to the plotter window for recording analog sensor data to CSV files. This feature is designed to minimize memory usage and prevent application crashes during long recording sessions. The implementation has been optimized to prevent GUI interference and ensure reliable operation through proper Qt thread management and cleanup handling.

## Features

- **Low Memory Footprint**: Records data with minimal RAM usage (only 30 samples buffered)
- **Automatic Saving**: Data is written to CSV every 30 seconds
- **4-Channel Recording**: All 4 analog inputs recorded simultaneously
- **Timestamped Data**: Each sample includes system timestamp
- **Background Operation**: Recording runs in background without blocking GUI
- **Configurable Save Location**: Choose where to save CSV files
- **Proper Thread Management**: QTimers with correct parent objects prevent GUI blocking
- **Reliable Cleanup**: Dual signal connections ensure proper window closure handling
- **Non-Blocking UI**: No blocking message boxes during operation

## Usage

### Starting a Recording

1. **Open Recorder Dialog**
   - Menu: `Tools → Record Analog Inputs`
   - Or use keyboard shortcut (if configured)

2. **Select Save File**
   - Click "Browse..." button
   - Choose save location and filename
   - Default filename format: `analog_inputs_YYYYMMDD_HHMMSS.csv`

3. **Start Recording**
   - Click "Start Recording" button
   - Recorder window will open showing recording status

### During Recording

- **Sampling Rate**: 1 sample per second (1 Hz)
- **Write Interval**: Every 30 seconds (30 samples per write)
- **Buffer Size**: 30 rows in RAM before flush
- **File Format**: CSV with headers

### Stopping a Recording

- Click "Stop Recording" button in recorder window
- OR close the recorder window
- Remaining buffered data will be automatically flushed to file

## CSV File Format

```csv
Timestamp,Analog_0_V,Analog_1_V,Analog_2_V,Analog_3_V
2025-10-20 14:30:00,2.45,1.23,3.67,0.89
2025-10-20 14:30:01,2.46,1.24,3.68,0.90
...
```

### Columns

- **Timestamp**: System time in format `YYYY-MM-DD HH:MM:SS`
- **Analog_0_V**: Channel 0 voltage reading
- **Analog_1_V**: Channel 1 voltage reading
- **Analog_2_V**: Channel 2 voltage reading
- **Analog_3_V**: Channel 3 voltage reading

## Technical Details

### Architecture

The recorder uses a robust architecture designed to prevent GUI interference:

#### QTimer Parent Objects
All QTimers are created with the parent window as their parent QObject:
```python
self.sample_timer = QTimer(parent_window)
self.flush_timer = QTimer(parent_window)
```

This ensures:
- Proper thread affinity (timers run in main thread)
- Automatic cleanup when window is destroyed
- No blocking of GUI event loop

#### Signal/Slot Management
Timers are properly cleaned up when stopping:
```python
self.sample_timer.stop()
self.sample_timer.disconnect()  # Remove all signal connections
self.flush_timer.stop()
self.flush_timer.disconnect()
```

#### Window Cleanup
Dual signal connections ensure reliable cleanup:
```python
self._recorder_window.finished.connect(self._on_recorder_window_closed)
self._recorder_window.destroyed.connect(self._on_recorder_window_destroyed)
```

#### Stale Reference Detection
The main app checks for stale window references before operations:
```python
if self._recorder_window is not None:
    try:
        self._recorder_window.isVisible()
    except RuntimeError:
        self._recorder_window = None  # Clear stale reference
```

### Memory Management

- **Buffer Size**: 30 samples (~1 KB)
- **Write Frequency**: Every 30 seconds
- **Total Memory Usage**: < 5 KB for recorder

### Performance

- **CPU Usage**: Minimal (timer-based sampling)
- **GUI Impact**: Non-blocking background operation (fixed timer parent issues)
- **File I/O**: Buffered writes prevent disk thrashing
- **Thread Safety**: All operations run in main GUI thread with proper timer affinity

### Error Handling

- **Arduino Disconnection**: Recording automatically stops
- **File Write Errors**: User notified, recording stopped
- **Missing Readings**: Logged to console, continues recording
- **Stale Window References**: Automatically detected and cleared
- **Timer Cleanup**: Proper signal disconnection prevents race conditions

## Comparison with Plotter Window

| Feature | Analog Recorder | Plotter Window |
|---------|----------------|----------------|
| Memory Usage | < 5 KB | 100-800 MB |
| Data Visualization | No | Yes |
| CSV Recording | Yes | Yes |
| Long Sessions | Stable | May crash |
| CPU Usage | Very Low | Moderate |
| GUI Responsiveness | No impact | Some impact |

## Troubleshooting

### "Arduino Not Connected" Error

**Problem**: Cannot start recording because Arduino is not connected

**Solution**:

- Check Arduino USB connection
- Verify green connection indicator in main window
- Restart application if needed

### File Write Errors

**Problem**: "Failed to write data to CSV" error

**Solution**:

- Check file is not open in another application
- Verify write permissions for save location
- Ensure sufficient disk space
- Try a different save location

### Recorder Already Running

**Problem**: Cannot start second recorder instance

**Solution**:

- Only one recorder can run at a time
- Close existing recorder window first
- Or raise existing recorder window to view status

### GUI Freezing or Button Colors Not Updating

**Problem**: Main GUI appears frozen or buttons don't show correct states during recording

**Solution**:

- This was a known issue that has been **fixed** in the current version
- QTimer parent objects now properly set to prevent thread affinity issues
- If you still experience this, restart the application
- Ensure you're running the latest version with the timer fixes

## Implementation Notes

### QTimer Thread Affinity

QTimers must have a parent QObject to establish proper thread affinity. The recorder implementation ensures:

- Timers are created with `parent_window` as parent
- This keeps timers in the main GUI thread
- Timer events don't block the event loop
- Automatic cleanup when parent is destroyed

Without a parent:

- Timer may run in any thread
- Timer events may be delivered to wrong thread
- Can cause GUI event loop blocking and freezing

### Signal/Slot Best Practices

The implementation follows Qt best practices:

- Always `disconnect()` timer signals before deletion
- Use both `finished` and `destroyed` signals for redundancy
- Check object validity before accessing after signals
- Handle `RuntimeError` gracefully when window is deleted

### Window Reference Management

Proper window lifecycle management:

- Store window reference in parent (`_recorder_window`)
- Clear reference in multiple cleanup paths
- Test validity before operations (`isVisible`, `isHidden`)
- Catch and handle `RuntimeError` when accessing deleted windows

### File Append Behavior

- **First Write**: Creates new file with header row
- **Subsequent Writes**: Appends data without header
- **File Exists**: Will append to existing file (no overwrite)

### Data Integrity

- All buffered data is flushed before stopping
- File writes are atomic (complete or fail)
- Partial buffers are written on close/stop

### Thread Safety

- Recording runs on Qt timer (main thread)
- File I/O is synchronous but infrequent
- No threading conflicts with GUI
- Proper timer parent ensures correct thread affinity

## Known Issues and Fixes

### Fixed Issues (Current Version)

The following issues have been resolved:

1. **GUI Update Freezing** ✅ FIXED
   - **Was**: Analog indicators stopped updating during recording
   - **Fix**: QTimers now have proper parent objects

2. **Button State Display** ✅ FIXED
   - **Was**: Buttons not showing correct colors for their states
   - **Fix**: Timer thread affinity corrected, events don't block GUI

3. **Stale Window References** ✅ FIXED
   - **Was**: App thought recorder was still open after closing
   - **Fix**: Dual signal connections (`finished` + `destroyed`) and validity checking

4. **Blocking Message Boxes** ✅ FIXED
   - **Was**: "Recording Started" dialog blocked GUI
   - **Fix**: Removed all blocking message boxes from recorder operation

5. **Timer Cleanup Issues** ✅ FIXED
   - **Was**: Timer signals not disconnected, causing race conditions
   - **Fix**: Explicit `disconnect()` calls in cleanup

### Verification Checklist

After starting a recording, verify:

- [ ] GUI analog indicators continue updating during recording
- [ ] Button colors update correctly while recorder is running
- [ ] Closing recorder window clears reference properly
- [ ] Opening new recording after closing previous one works
- [ ] No "Recorder Already Running" error after closing window
- [ ] No RuntimeError exceptions in console
- [ ] CSV file contains correct voltage data
- [ ] System remains responsive during recording

## Future Enhancements

Potential improvements for future versions:

- [ ] Configurable sampling rate
- [ ] Configurable buffer size
- [ ] Multiple simultaneous recordings
- [ ] Real-time data preview
- [ ] Export to other formats (HDF5, JSON)
- [ ] Data compression
- [ ] Automatic file rotation
- [ ] Email notifications on completion

## Related Files

- `python/widgets/analog_recorder.py` - Recorder implementation
- `python/app.py` - Main window integration (lines 2704-2776)
- `docs/TECHNICAL_MANUAL.md` - System documentation
- `docs/PLOTTER_MEMORY_ANALYSIS.md` - Analysis of plotter memory issues
- `docs/PLOTTER_IMPROVEMENTS_SUMMARY.md` - Plotter optimization summary

## Version History

### Current Version (Post-Fixes)
- **Date**: October 21, 2025
- **Changes**: Fixed QTimer parent issues, added proper cleanup, removed blocking dialogs
- **Status**: Stable, all known GUI interference issues resolved

### Initial Version
- **Date**: October 20, 2025
- **Changes**: Initial implementation with basic CSV recording
- **Issues**: GUI freezing, stale references, blocking dialogs

---

**Last Updated**: October 28, 2025
