# PowerShell wrapper for User Account Management CLI
# Makes it easier to run from anywhere on Windows

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonScript = Join-Path $ScriptDir "manage_users.py"

# Check if Python script exists
if (-not (Test-Path $PythonScript)) {
    Write-Host "❌ Error: manage_users.py not found at $PythonScript" -ForegroundColor Red
    exit 1
}

# Run Python script with all arguments
& python $PythonScript $args
