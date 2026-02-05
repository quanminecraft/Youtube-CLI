#!/bin/bash

# YouTube CLI Linux Startup Script

# 1. Resize Terminal (148 columns, 46 rows)
# Uses ANSI escape sequence \e[8;ROW;COLt
printf '\e[8;46;148t'

# 2. Navigate to script directory
cd "$(dirname "$0")"

# 3. Check for Python
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo -e "\033[0;31mError: Python not found!\033[0m"
    echo "Please install python3."
    read -p "Press Enter to exit..."
    exit 1
fi

# 4. Optional: Virtual Environment Check
# (Uncomment if you use a venv, otherwise runs in system/user python context)
# if [ -d "venv" ]; then
#     source venv/bin/activate
# fi

# 5. Run Application
$PYTHON_CMD main.py

# 6. Check Exit Code
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo -e "\n\033[0;31mProcess exited with error (Code: $EXIT_CODE).\033[0m"
    read -p "Press Enter to close..."
fi

# 7. Auto-close functionality
# If execution was successful (EXIT_CODE 0), the script ends here, 
# and the terminal window typically closes (depends on terminal emulator settings).
