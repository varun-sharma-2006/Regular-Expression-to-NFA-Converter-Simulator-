@echo off
REM ============================================================
REM  AutomataAI launcher - just double-click this file.
REM  First run: creates the virtual environment and installs
REM  the packages (needs internet once). Then starts the server
REM  and opens the app in your browser.
REM ============================================================
cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo ERROR: Python was not found. Install Python 3 from python.org
        echo and tick "Add python.exe to PATH" during installation.
        pause
        exit /b 1
    )
    echo Installing packages...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Package installation failed. Check your internet connection.
        pause
        exit /b 1
    )
)

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo Created backend\.env  - put your API key there to enable the AI features.
)

echo.
echo Starting AutomataAI at http://127.0.0.1:5000   (close this window to stop)
echo.
REM open the browser after 3 seconds, when the server is ready
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:5000"
".venv\Scripts\python.exe" app.py
pause
