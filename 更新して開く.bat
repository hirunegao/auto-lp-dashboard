@echo off
rem GSC/GA4の最新データを取得し、GitHub Pagesにも公開してダッシュボードを開く
cd /d "%~dp0..\src"
python -m auto_lp.refresh_dashboard
cd /d "%~dp0"
git add data.js own_data.js index.html
git commit -m "Update dashboard data" >nul 2>&1
git push origin main
start "" "https://hirunegao.github.io/auto-lp-dashboard/"
pause
