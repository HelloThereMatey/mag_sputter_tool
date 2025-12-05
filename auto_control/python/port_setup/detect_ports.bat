@echo off
REM Wrapper script for MFC port detection utility (Windows)
REM Usage: detect_ports.bat [--arduino-port COMX] [--dry-run] [--verbose]

echo Running MFC port detection...
python detect_mfc_ports.py %*
