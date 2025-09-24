.PHONY: init migrate seed-roles run test

init:
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

migrate:
python manage.py migrate

seed-roles:
python manage.py roles_seed

run:
python manage.py runserver 0.0.0.0:8000

test:
python manage.py test
