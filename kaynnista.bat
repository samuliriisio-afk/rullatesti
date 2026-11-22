@echo off
REM Käynnistää Rullat Exceliin -sovelluksen Windowsissa. Ensimmäisellä kerralla asentaa tarvittavat paketit.
cd /d "%~dp0"
if not exist venv (
  python -m venv venv
  call venv\Scripts\activate
  pip install -r requirements.txt
) else (
  call venv\Scripts\activate
)
echo.
echo Sovellus kayntiin osoitteessa http://localhost:8000
echo Sulje tama ikkuna pysayttaaksesi sovelluksen.
python app.py
pause
