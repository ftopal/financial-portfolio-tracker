@echo off
echo Starting Celery Worker and Beat...
start cmd /k ".venv\Scripts\celery -A portfolio_project worker -l info --pool=solo"
timeout /t 5
start cmd /k ".venv\Scripts\celery -A portfolio_project beat -l info"
echo Celery started!