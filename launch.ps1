# Set Output Encoding to UTF-8 to fix font/emoji display
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Title
$Host.UI.RawUI.WindowTitle = "YouTube Music CLI"

# Check for Python
if (Get-Command "python" -ErrorAction SilentlyContinue) {
    python main.py
} elseif (Get-Command "py" -ErrorAction SilentlyContinue) {
    py main.py
} else {
    Write-Host "Error: Python not found in PATH." -ForegroundColor Red
    Write-Host "Please install Python or add it to your PATH."
    Read-Host "Press Enter to exit..."
}

# Keep window open if script crashes or finishes (optional, mainly for debugging)
if ($LastExitCode -ne 0) {
    Read-Host "Process exited with error. Press Enter to close..."
}
