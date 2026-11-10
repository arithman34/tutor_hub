#!/bin/bash
set -e

if [[ "$1" == "gunicorn" ]]; then
  python manage.py migrate
fi

exec "$@"
