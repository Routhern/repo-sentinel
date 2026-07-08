@echo off
rem cmd에서 실행: 저장소를 어디에 두든 uv만 있으면 동작한다.
cd /d "%~dp0.."
uv run repo-sentinel %*
