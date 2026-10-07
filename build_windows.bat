@echo off
setlocal

where python >nul 2>&1
if errorlevel 1 (
  echo Python bulunamadi. Python 3.12 kurulu olmali.
  pause
  exit /b 1
)

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install "pyinstaller>=6,<7"
python -m unittest discover -s tests -v
if errorlevel 1 (
  echo Testler basarisiz. EXE uretilmedi.
  pause
  exit /b 1
)

pyinstaller --noconfirm --clean --onefile --windowed --name UmutScanner app.py
if errorlevel 1 (
  echo EXE build basarisiz.
  pause
  exit /b 1
)

echo.
echo Hazir: dist\UmutScanner.exe
pause
