#! /bin/sh
# run migrations
python manage.py migrate
# run server

if [ "$MODE" = "development" ]; then
    echo "Running Development Server...\n"
	python manage.py runserver 0.0.0.0:5005
elif [ "$MODE" = "production" ]; then
    echo "Running Production Server...\n"
	gunicorn --config gunicorn-cfg.py core.wsgi
fi