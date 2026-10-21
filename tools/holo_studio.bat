@echo off
rem Holo Studio launcher: double-click to start, then use the page that opens in your browser.
rem Needs the Python environment with this repo's bench extras (pip install -e ".[bench]").
rem Either start it from a prompt where that environment is active, or set HOLO_PYTHON once to that
rem environment's python.exe (System > Environment Variables), e.g. ...\envs\<name>\python.exe
rem (quotes around the path are fine). To try it without the projector: set DLP_NO_HARDWARE=1 first.
cd /d "%~dp0.."
if defined HOLO_PYTHON set "HOLO_PYTHON=%HOLO_PYTHON:"=%"
if defined HOLO_PYTHON goto custom
python -m studio %*
goto done
:custom
"%HOLO_PYTHON%" -m studio %*
:done
echo.
if %ERRORLEVEL% NEQ 0 goto failed
echo Holo Studio has stopped. The projector is dark and the rig is released.
goto end
:failed
echo Holo Studio did not start, or stopped with an error (see above).
echo If another studio is already running, open its page instead (http://127.0.0.1:8765/ by default).
:end
pause
