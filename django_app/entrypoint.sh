#!/bin/bash
set -e

if [[ "$1" == "gunicorn" ]]; then
  python manage.py migrate
  # Log any Zoom lessons missed while no server was running (e.g. a Spot
  # interruption). In the background, so a slow Zoom never delays startup.
  python manage.py zoom_catch_up &
fi

exec "$@"
