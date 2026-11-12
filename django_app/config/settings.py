"""
Django settings for the TutorHub rewrite.

Mirrors the FastAPI app's .env-based config convention: everything that
varies per environment is read from the environment, with sane local
defaults.
"""

import re
import sys
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent
RUNNING_TESTS = "test" in sys.argv or "pytest" in sys.modules

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me-0123456789")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "accounts",
    "students",
    "tutoring_sessions",
    "billing",
    "calendar_integration",
    "analytics",
    "assistant",
    "web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
    {
        # The public homepage and privacy policy (templates/), in Jinja2 as
        # carried over from the FastAPI app. Every other page is the React app.
        "BACKEND": "django.template.backends.jinja2.Jinja2",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {
            "environment": "config.jinja2_env.environment",
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

if RUNNING_TESTS:
    # Avoids requiring a local Postgres instance just to run the test suite.
    # Nothing in the current models relies on Postgres-only features.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "tutorhub"),
            "USER": os.environ.get("POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }

AUTH_USER_MODEL = "accounts.User"

# The FastAPI app hashed passwords with passlib's plain bcrypt (format
# "$2b$12$..."), not Django's default PBKDF2. Adding BCryptPasswordHasher
# (not in Django's default list) lets check_password() verify those legacy
# hashes after a data import; new/changed passwords still hash with the
# first entry below (Django's PBKDF2 default).
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.BCryptPasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

REST_FRAMEWORK = {
    # A JWT from the Authorization header (API clients) or the httponly
    # access_token cookie (the browser app, CSRF-checked).
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "accounts.authentication.CookieJWTAuthentication",
    ),
    # Every view gets both unless it sets its own. The demo account can read
    # everything but change nothing (see accounts/permissions.py).
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
        "accounts.permissions.DemoIsReadOnly",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "TutorHub API",
    "DESCRIPTION": "Students, sessions, billing, calendar and analytics for an independent tutor.",
    "VERSION": "1.0.0",
    # Serve the schema separately rather than listing it inside itself.
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAuthenticated"],
    # Swagger UI assets come from drf-spectacular-sidecar, not a CDN.
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "COMPONENT_SPLIT_REQUEST": True,
    # Stripped from paths to name operations (students_list) and tag them by
    # area. Set explicitly: by default it's guessed from every route, so one
    # API view outside /api/v1 would rename them all.
    "SCHEMA_PATH_PREFIX": r"/api/v1",
}

# Cookies are HTTPS-only in production. Local runserver is plain HTTP, so
# they can't be there.
SECURE_COOKIES = not DEBUG
CSRF_COOKIE_SECURE = SECURE_COOKIES
SESSION_COOKIE_SECURE = SECURE_COOKIES

# The read-only demo account behind the homepage's "Try the demo" button
# (accounts/demo.py). It's created on the first click and refilled with
# fresh made-up records once a week. Set DEMO_ENABLED=false to hide it.
DEMO_ENABLED = os.environ.get("DEMO_ENABLED", "true").lower() == "true"
DEMO_EMAIL = "demo@tutorhub.test"
# Shared by every visitor, so it caps what the demo can cost in AI calls.
DEMO_AI_DAILY_LIMIT = int(os.environ.get("DEMO_AI_DAILY_LIMIT", "20"))

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# The manifest storage serves content-hashed filenames (safe to cache
# forever), but static() raises if collectstatic hasn't run. Tests render
# templates without a build, so they use plain filenames.
STORAGES = {
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if RUNNING_TESTS
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}


def _immutable_static_file(path: str, url: str) -> bool:
    """Files WhiteNoise may tell browsers to cache forever: those whose name
    changes whenever their content does. That's Django's hashed copies
    (app.2bb0a3640c85.css) and Vite's bundles for the React app
    (spa/assets/index-B1x9fQzA.js). Never spa/index.html, which keeps its name."""
    return bool(re.match(r"^.+\.[0-9a-f]{12}\..+$", url)) or "/spa/assets/" in url


WHITENOISE_IMMUTABLE_FILE_TEST = _immutable_static_file

# Behind the Cloudflare Tunnel (production) / an ALB, the real scheme arrives
# as X-Forwarded-Proto, not on the connection itself.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# OpenAI: TutorHub AI and Zoom summary parsing
# Shown on the public privacy policy. Falls back to the developer's GitHub
# profile when unset.
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ASSISTANT_MODEL = os.environ.get("ASSISTANT_MODEL", "gpt-4o-mini")

# Google Calendar integration
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/calendar/callback")
GOOGLE_CALENDAR_TIMEZONE = os.environ.get("GOOGLE_CALENDAR_TIMEZONE", "Europe/London")
# Where Google's OAuth callback sends the browser afterwards. The React app is
# served by Django under /app, so a same-site path works in every environment.
FRONTEND_URL = os.environ.get("FRONTEND_URL", "/app")

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "")
