import os
import secrets
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
PRIVATE_DIR = Path(os.environ.get("NOTICEBOARD_PRIVATE", BASE_DIR / "private"))
load_dotenv(BASE_DIR / "runtime/local.env")
RUNTIME_DIR = Path(os.environ.get("NOTICEBOARD_RUNTIME", BASE_DIR / "runtime"))
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
_secret = RUNTIME_DIR / ".secret"
if not _secret.exists():
    try:
        fd = os.open(_secret, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(secrets.token_urlsafe(48))
    except FileExistsError:
        pass
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or _secret.read_text().strip()
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "procurement",
    "ninja",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True}]
ROOT_URLCONF = "noticeboard.urls"
WSGI_APPLICATION = "noticeboard.wsgi.application"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": RUNTIME_DIR / "noticeboard.sqlite3",
        "OPTIONS": {"timeout": 30},
    }
}
if url := os.environ.get("DATABASE_URL"):
    parsed = urlparse(url)
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname,
        "PORT": parsed.port or 5432,
        "CONN_MAX_AGE": 60,
    }
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/assets/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = (
    [BASE_DIR / "frontend" / "dist" / "assets"]
    if (BASE_DIR / "frontend/dist/assets").exists()
    else []
)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = os.environ.get("HTTPS", "0") == "1"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
CSRF_TRUSTED_ORIGINS = [s for s in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if s]
if os.environ.get("TRUST_HTTPS_PROXY", "0") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SEARCH_URL = os.environ.get("OPENSEARCH_URL", "")
SEARCH_INDEX = "noticeboard-current"
EMBEDDING_MODEL = os.environ.get(
    "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
MODEL_CACHE = RUNTIME_DIR / "models"
OPS_TOKEN = os.environ.get("NOTICEBOARD_OPS_TOKEN", "")
LLM_URL = os.environ.get("NOTICEBOARD_LLM_URL", "")
LLM_MODEL = os.environ.get("NOTICEBOARD_LLM_MODEL", "")
LLM_KEY = os.environ.get("NOTICEBOARD_LLM_KEY", "")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
