from pathlib import Path

from config import Config
from flask import Flask, abort, flash, redirect, render_template, request, session
from flask.helpers import url_for
from flask_flatpages import FlatPages
from flask_simplemde import SimpleMDE
from flask_uploads import IMAGES, UploadSet, configure_uploads
from itsdangerous import TimedJSONWebSignatureSerializer
from werkzeug.datastructures import CombinedMultiDict
from werkzeug.utils import secure_filename

from teamblog.utils import (
    is_safe_url,
    login_required,
    send_invite_email,
    send_login_email,
)

from .forms import AdminForm, InviteForm, LoginForm, RegisterForm, UploadForm, photos
from .models import User, db

app = Flask(__name__, instance_relative_config=False)
app.config.from_object(Config)

# Initialize Plugins
db.init_app(app)
pages = FlatPages(app)
SimpleMDE(app)
# photos = UploadSet("photos", IMAGES)  # This is also in forms?
configure_uploads(app, photos)


@app.before_request
def before_request():
    session.permanent = True


# Process available tags and make it available to every render for base.j2
@app.context_processor
def inject_tags():
    tags = set(page["tag"] for page in pages)
    return dict(tags=tags)


with app.app_context():
    # Setup the database
    db.create_all()

    user = User.query.filter_by(email=app.config["BLOG_ADMIN"]).first()
    if not user:
        print("Sending invite to Admin...")
        send_invite_email(app.config["BLOG_ADMIN"], "Admin")


# Blog routes
@app.route("/")
def index():
    latest = sorted(pages, reverse=True, key=lambda p: p.meta["date"])

    if not "welcome" in session:
        flash("I'm happy you made it!", "Welcome!")
        session["welcome"] = True

    return render_template("index.j2", pages=latest[:2])


@app.route("/blog")
def blog():
    latest = sorted(pages, reverse=True, key=lambda p: p.meta["date"])
    return render_template("blog.j2", pages=latest)


@app.route("/blog/<path:path>/", methods=["GET", "POST"])
def page(path):
    page = pages.get_or_404(path)

    if request.method == "POST" and "user_id" in session:
        page_fullpath = (
            Path()
            / app.config["FLASK_APP"]
            / app.config["FLATPAGES_ROOT"]
            / secure_filename(page.path + ".md")
        )
        try:
            page_fullpath.unlink()
            FlatPages.reload(pages)
            flash(f"Blog post {page.path} has been deleted!", "Info")
            return redirect(url_for("index"))
        except OSError:
            abort(404)

    return render_template("page.j2", page=page)


@app.route("/blog/tag/<string:tag>/")
def tag(tag):
    tagged = sorted(
        [p for p in pages if tag == p.meta.get("tag", None)],
        reverse=True,
        key=lambda p: p.meta["date"],
    )
    return render_template("tag.j2", pages=tagged, tag=tag)


# Admin routes
@app.route("/admin", methods=["GET", "POST"])
@login_required()
def admin():
    # Handle forwarding if redirected here after login
    if session.get("next_url"):
        next_url = session.get("next_url")
        session.pop("next_url", None)
        return redirect(next_url)

    # Process form data
    form = AdminForm()
    form.tag.choices = app.config["BLOG_TAGS"]
    if form.validate_on_submit():
        pages_directory = (
            Path() / app.config["FLASK_APP"] / app.config["FLATPAGES_ROOT"]
        )
        if not pages_directory.exists():
            abort(500)

        result = form.save(
            template="page_contents.j2",
            directory=pages_directory,
        )
        if result:
            FlatPages.reload(pages)
            flash("Blog entry posted successfully!", "Info")
        else:
            flash("Something went wrong.  Please try again shortly.", "Error")

        return redirect(url_for("admin"))

    else:
        if form.errors:
            flash(
                "Please correct errors detected in your form",
                "Error",
            )

    return render_template("admin.j2", form=form)


# Login routes
@app.route("/admin/login_request", methods=["GET", "POST"])
def login_request():
    # Redirect if user is already logged in
    if "user_id" in session:
        return redirect(url_for("admin"))

    # Process form data
    form = LoginForm()
    if form.validate_on_submit():
        user = form.get_user()
        if user:
            send_login_email(user)

        return render_template("email_sent.j2")

    return render_template("login.j2", form=form)


@app.route("/admin/login", methods=["GET"])
def login():
    # Redirect if user is already logged in
    if "user_id" in session:
        return redirect(url_for("admin"))

    # Retrieve token provided via email and process login request
    token = request.args.get("token")

    if token:
        user = User.deserialize_token(token)

        if user is None or not user.is_active():
            flash("Your token has expired.", "Error")
            return redirect(url_for("login_request"))

        session["user_id"] = user.id
        session["displayname"] = user.displayname
        user.update_activity_tracking(request.remote_addr)
        flash("You have logged in.", "Info")

        return redirect(url_for("admin"))

    return redirect(url_for("index"))


@app.route("/admin/logout")
def logout():
    if "user_id" in session:
        session.pop("user_id")

    return redirect(url_for("index"))


@app.route("/admin/invite", methods=["GET", "POST"])
@login_required()
def invite():
    # Process form data
    form = InviteForm()
    if form.validate_on_submit():
        result = form.invite_user()
        if result:
            flash("New team member invited!", "Hooray!")
            return redirect(url_for("admin"))
        else:
            flash(
                "Something has gone wrong.  Please try again in a few minutes.", "Error"
            )

    return render_template("invite.j2", form=form)


@app.route("/admin/register", methods=["GET", "POST"])
def register():
    # Redirect if user is already logged in
    if "user_id" in session:
        return redirect(url_for("admin"))

    # Get token provided in email and decode it
    token = request.args.get("token")

    private_key = TimedJSONWebSignatureSerializer(app.config["SECRET_KEY"])
    try:
        decoded_payload = private_key.loads(token)

        email = decoded_payload.get("email")
        displayname = decoded_payload.get("displayname")
    except Exception:
        return abort(400)

    # Pass decoded payload into registration form
    form = RegisterForm(email=email, displayname=displayname)
    if form.validate_on_submit():
        # Override email coming back from form
        user = form.create_user(email=email)

        if user:
            session["user_id"] = user.id
            session["displayname"] = user.displayname
            user.update_activity_tracking(request.remote_addr)
            flash("Account created", "Info")

            return redirect(url_for("admin"))

    return render_template("register.j2", form=form)


# File management routes
@app.route("/images", methods=["GET"])
@login_required()
def images():
    # This would probably been a LOT easier to just do by hand...
    images_path = (
        Path()
        / app.config["FLASK_APP"]
        / url_for("static", filename=app.config["BLOG_UPLOAD_PATH"])[1:]
    )
    images = [image.name for image in images_path.glob("*")]

    usage = {}
    for image in images:
        usage[image] = len(
            [
                page.path
                for page in pages
                if image in page["image"] or image in page.html
            ]
        )

    form = UploadForm()

    return render_template(
        "images.j2",
        images=images,
        image_path=app.config["BLOG_UPLOAD_PATH"],
        usage=usage,
        form=form,
    )


@app.route("/images/upload", methods=["POST"])
@login_required()
def image_upload():
    # The file data needs to be combined with the form to validate and process the upload
    file_request = CombinedMultiDict((request.files, request.form))

    # This is a necessary because we are processing the form outside of the original route
    if UploadForm(file_request).validate_on_submit():
        filename = UploadForm(file_request).save()
        if filename:
            flash(f"Successfully uploaded {filename}", "Info")
        else:
            flash(
                "There was a problem with the file provided.  Is it an image?", "Error"
            )

    else:
        flash("There was a problem uploading your file.  Is it an image?", "Error")

    return redirect(url_for("images"))


@app.route("/images/delete/<string:name>", methods=["GET"])
@login_required()
def image_delete(name):
    if not name:
        abort(400)

    image_fullpath = (
        Path()
        / app.config["FLASK_APP"]
        / url_for("static", filename=app.config["BLOG_UPLOAD_PATH"])[1:]
        / secure_filename(name)
    )

    usage = len(
        [page.path for page in pages if name in page["image"] or name in page.html]
    )

    if usage == 0:
        try:
            image_fullpath.unlink()
            flash(f"Image {name} has been deleted!", "Info")
            return redirect(url_for("images"))
        except OSError:
            abort(404)

    flash(f"Unable to delete {name}.  Image in use.", "Error")
    return redirect(url_for("images"))


# Jinja2 Filters
@app.template_filter("dateformat")
def datetimeformat(value, format="%b %-d, %Y"):
    return value.strftime(format)
