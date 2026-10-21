@echo off
rem Holo Studio launcher: double-click to start, then use the page that opens in your browser.
rem Needs the Python environment with this repo's bench extras (pip install -e ".[bench]").
rem Either start it from a prompt where that environment is active, or set HOLO_PYTHON once to that
rem environment's python.exe (System > Environment Variables), e.g. ...\envs\<name>\python.exe
rem To try it without the projector: set DLP_NO_HARDWARE=1 before starting (preview only).
cd /d "%~dp0.."
if defined HOLO_PYTHON (
  "%HOLO_PYTHON%" -m studio %*
) else (
  python -m studio %*
)
echo.
echo Holo Studio has stopped. The projector is dark and the rig is released.
pause
