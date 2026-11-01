@echo off
REM Phase 1 backfill launcher: runs unattended and restarts after crashes or network loss.
REM Stops when complete (exit 0) or when the disk is full (exit 2). Safe to close and re-run.
REM Progress: python -m nowcast.flows.backfill status    Log: data\logs\backfill.log
cd /d "%~dp0"
set ATTEMPT=0
:loop
set /a ATTEMPT+=1
echo [%date% %time%] backfill attempt %ATTEMPT%
python -m nowcast.flows.backfill run %*
set CODE=%ERRORLEVEL%
if %CODE%==0 (
  echo [%date% %time%] backfill complete.
  goto end
)
if %CODE%==2 (
  echo [%date% %time%] stopped: not enough free disk. Free space and run this file again.
  goto end
)
if %ATTEMPT% GEQ 50 (
  echo [%date% %time%] giving up after 50 attempts. See data\logs\backfill.log
  goto end
)
echo [%date% %time%] exit code %CODE%, restarting in 5 minutes...
timeout /t 300 /nobreak >nul
goto loop
:end
pause
