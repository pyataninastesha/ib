python manage.py migrate


## Быстрый запуск
### Windows
`run_dev.bat`

### Linux/Mac
`bash run_dev.sh`

## Если видите ошибку `no such column ...organization_id`
Это значит, что база данных была создана до добавления организаций.
Сделайте одно из двух:
1) Выполните миграции: `python manage.py migrate`
2) Если это тестовый запуск — удалите `db.sqlite3` и снова выполните `python manage.py migrate`
