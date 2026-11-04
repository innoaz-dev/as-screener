@echo off
chcp 65001 >nul
cd /d "%~dp0"
uv run --python 3.12 tests\run_regression.py %*
pause
