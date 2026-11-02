@echo off
cd /d "%~dp0backend"
if not exist .venv (
  echo Creating Python virtual environment...
  python -m venv .venv
)
call .venv\Scripts\activate
pip install -r requirements.txt
echo.
echo  API:      http://localhost:5000
echo  Swagger:  http://localhost:5000/api/docs
echo.
python run.py
pause
