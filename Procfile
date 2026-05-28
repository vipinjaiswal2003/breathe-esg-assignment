web: cd frontend && npm install && npm run build && cd .. && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2
release: python manage.py migrate && python manage.py seed_data
