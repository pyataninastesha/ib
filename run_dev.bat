@echo off
REM One-click run for Windows
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
