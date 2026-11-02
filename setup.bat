@echo off
cd /d "%~dp0"
echo Creating virtual environment...
python -m venv .venv
call .venv\Scripts\activate.bat
echo Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
echo Initializing database with demo data...
python -m core.seed
echo.
echo Setup complete. Start the app with run.bat
pause
