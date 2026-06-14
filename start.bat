@echo off
title Computer Use Agent
cd /d "%~dp0"
python -X utf8 -m computer_use_agent %*
pause
