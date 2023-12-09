import os
from datetime import timedelta
from pathlib import Path


class Config:
    """Set Flask configuration vars."""

    # General Config
    FLASK_APP = os.environ.get("FLASK_APP") or "application"
    SECRET_KEY = os.environ.get("SECRET_KEY") or "secret_key"

    ENV = os.environ.get("FLASK_ENV") or "development"
    if ENV == "development":
        DEBUG = True

    if os.environ.get("SESSION_LIFETIME"):
        PERMANENT_SESSION_LIFETIME = timedelta(
            minutes=int(os.environ.get("SESSION_LIFETIME"))
        )

    # SERVER_NAME = os.environ.get("SERVERNAME") or "localhost:5000"
    MAX_CONTENT_LENGTH = (
        os.environ.get("FMAX_CONTENT_LENGTH") or 16 * 1024 * 1024
    )  # 16m upload limit

    # SQLAlchemy Config
    ## Ensure the instance folder exists
    INSTANCE_PATH = os.environ.get("INSTANCE_PATH") or Path.cwd() / "instance"
    INSTANCE_PATH.mkdir(exist_ok=True)

    database_url = f"sqlite:///{INSTANCE_PATH}/{FLASK_APP}.sqlite"

    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Resend Config
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY")

    # FlatPages Config
    FLATPAGES_ROOT = "pages"
    FLATPAGES_EXTENSION = ".md"

    # SimpleMDE Config
    SIMPLEMDE_JS_IIFE = True
    SIMPLEMDE_USE_CDN = True

    # Blog Config
    BLOG_ADMIN = os.environ.get("BLOG_ADMIN_EMAIL")
    BLOG_CONTACT_EMAIL = os.environ.get("BLOG_CONTACT_EMAIL")
    BLOG_TAGS = ["Random", "Tech", "Programming", "Gaming", "Stuff"]
    BLOG_UPLOAD_PATH = "uploads"

    # Flask-Reuploaded Config
    UPLOADED_PHOTOS_DEST = Path() / FLASK_APP / "static" / BLOG_UPLOAD_PATH
