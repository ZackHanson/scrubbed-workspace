@echo off
cd /d "%~dp0"
python review.py
if errorlevel 1 pause
