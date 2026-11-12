"""Serves the React app (spa/) at /app/.

The app routes in the browser, so every /app/... URL gets the same
index.html; React Router then shows the right page. Its JS and CSS bundles
are ordinary static files under /static/spa/ (Vite builds into static/spa/).
"""

from functools import lru_cache

from django.conf import settings
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_safe

NOT_BUILT = "The React app hasn't been built. Run `npm run build` in spa/ (or `npm run dev` and open http://localhost:5173/app/)."


def _read_index() -> str | None:
    path = finders.find("spa/index.html")
    if path is None:
        return None
    with open(path, encoding="utf-8") as file:
        return file.read()


# index.html only changes on deploy, so production reads it once. Locally it's
# re-read on every request, so a fresh `npm run build` shows up straight away.
_cached_index = lru_cache(maxsize=1)(_read_index)


@require_safe
@never_cache  # Always fetch index.html fresh, so a deploy's new bundle names are picked up.
@ensure_csrf_cookie  # The app's first unsafe request then already has a CSRF token.
def spa_index(request, path=""):
    html = _read_index() if settings.DEBUG else _cached_index()
    if html is None:
        return HttpResponse(NOT_BUILT, status=503, content_type="text/plain; charset=utf-8")
    return HttpResponse(html)
