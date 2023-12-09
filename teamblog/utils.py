import imghdr
from functools import wraps
from urllib.parse import urljoin, urlparse

import resend
from flask import current_app, flash, redirect, request, session, url_for
from flask.templating import render_template

resend.api_key = current_app.config["RESEND_API_KEY"]


def is_safe_url(target):
    """
    A function that ensures that a redirect target will lead to the same server
    A common pattern with form processing is to automatically redirect back to
    the user. There are usually two ways this is done: by inspecting a next URL
    parameter or by looking at the HTTP referrer. Unfortunately you also have to
    make sure that users are not redirected to malicious attacker's pages and
    just to the same host.
    Source: http://flask.pocoo.org/snippets/62/ (No longer hosted by the project)
    Archive: https://web.archive.org/web/20190128005233/http://flask.pocoo.org/snippets/62
    """
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


def login_required(
    target="login_request",
    msg="You need to be logged in to view that page.",
):
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if not session.get("user_id"):
                flash(msg)
                return redirect(url_for(target))
            return fn(*args, **kwargs)

        return decorated_view

    return wrapper


def send_login_email(user):
    params = {
        "from": current_app.config["BLOG_CONTACT_EMAIL"],
        "to": [user.email],
        "subject": "TeamBlog Login Link",
        "html": render_template(
            "login_email.j2",
            name=user.displayname,
            link=url_for("login", token=user.serialize_token(), _external=True),
        ),
    }

    try:
        r = resend.Emails.send(params)
        return True

    except Exception as e:
        print(str(e))
        return False


def send_invite_email(email, displayname):
    from itsdangerous import TimedJSONWebSignatureSerializer

    def create_token(email, displayname, expiration=3600):
        private_key = current_app.config["SECRET_KEY"]

        serializer = TimedJSONWebSignatureSerializer(private_key, expiration)
        return serializer.dumps({"email": email, "displayname": displayname}).decode(
            "utf-8"
        )

    try:
        register_link = url_for(
            "register", token=create_token(email, displayname), _external=True
        )
    except:
        # This is dirty but the app is not all the way up yet so url_for is not generating proper urls
        register_link = f"http://{current_app.config['SERVER_NAME']}/admin/register?token={create_token(email, displayname)}"

    params = {
        "from": current_app.config["BLOG_CONTACT_EMAIL"],
        "to": [email],
        "subject": "You've been invited to use TeamBlog!",
        "html": render_template(
            "register_email.j2",
            name=displayname,
            link=register_link,
        ),
    }

    try:
        r = resend.Emails.send(params)
        return True

    except Exception as e:
        print(str(e))
        return False


# From https://blog.miguelgrinberg.com/post/handling-file-uploads-with-flask
def validate_image(stream):
    # Read start of file stream and reset back to the start
    header = stream.read(512)
    stream.seek(0)

    # Determine file type
    format = imghdr.what(None, header)
    if not format:
        return False

    return True
