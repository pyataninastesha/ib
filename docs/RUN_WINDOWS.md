# Запуск (Windows)

1) Активировать окружение (если .venv):
```powershell
.\.venv\Scripts\Activate.ps1
```

2) Если миграции ломались ранее — удалите базу и создайте заново:
```powershell
del db.sqlite3
python manage.py migrate
```

3) Запуск:
```powershell
python manage.py runserver
```
