@echo off
rem GSC/GA4の最新データを取得してダッシュボードを開く
cd /d "%~dp0..\src"
python -m auto_lp.refresh_dashboard
start "" "%~dp0index.html"
pause
