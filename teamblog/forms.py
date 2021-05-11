from datetime import date

from flask import current_app
from flask.templating import render_template
from flask_uploads import IMAGES, UploadNotAllowed, UploadSet
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename
from wtforms import (
    DateField,
    Label,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
    ValidationError,
)
from wtforms.validators import URL, DataRequired, Email

from .models import User, db
from .utils import send_invite_email, validate_image

photos = UploadSet("photos", IMAGES)


class InviteForm(FlaskForm):
    email = StringField(
        "Email Address",
        validators=[Email(message="Please provide a valid email address")],
    )
    displayname = StringField("Display name", validators=[DataRequired()])
    submit = SubmitField("Sign in")

    def invite_user(self):
        user = User.query.filter_by(email=self.email.data).first()

        if not user:
            result = send_invite_email(self.email.data, self.displayname.data)

        return True if result else False


class LoginForm(FlaskForm):
    email = StringField(
        "Email Address",
        validators=[Email(message="Please provide a valid email address")],
    )
    submit = SubmitField("Sign in")

    def get_user(self):
        user = User.query.filter_by(email=self.email.data).first()
        if not user:
            # Normally we would set an error to display but, in this case, we are always going to send an "Email sent" message
            return None
        return user


class RegisterForm(FlaskForm):
    email = StringField(
        "Email address",
        validators=[
            Email(
                message="Please provide a valid email address",
                check_deliverability=True,
            )
        ],
    )
    displayname = StringField("Display name", validators=[DataRequired()])
    submit = SubmitField("Register")

    def create_user(self, email=None):
        if not email:
            email = self.email.data

        user = User(email=email)
        user.displayname = self.displayname.data
        db.session.add(user)
        try:
            db.session.commit()
            return user
        except IntegrityError:
            self.email.errors.append("This email address is already in use")
            return None


class AdminForm(FlaskForm):
    title = StringField("Blog Title", validators=[DataRequired()])
    image = StringField(
        "Image", validators=[URL(message="Please provide a valid URL"), DataRequired()]
    )

    def validate_image(form, field):
        if not field.data[-3:] in IMAGES and not field.data[-4:] in IMAGES:
            raise ValidationError("URL must reference an image")

    date = DateField(
        "Date (format = YYYY-MM-DD)", default=date.today, validators=[DataRequired()]
    )
    tag = SelectField("Tag", validators=[DataRequired()])
    summary = TextAreaField("Summary", validators=[DataRequired()])
    markdown_text = TextAreaField("Content", validators=[DataRequired()])
    submit = SubmitField("Save Blog Entry")

    def save(self, template=None, directory=None):
        filename = directory / secure_filename(self.title.data + ".md")

        content = render_template(
            template,
            title=self.title.data,
            image_url=self.image.data,
            date=self.date.data,
            tag=self.tag.data,
            summary=self.summary.data,
            markdown_text=self.markdown_text.data,
        )

        if not filename.exists():
            with open(filename, "w") as fp:
                fp.write(content)

            return True

        else:
            return False


class UploadForm(FlaskForm):
    upload = FileField(
        "image", validators=[FileRequired(), FileAllowed(photos, "Images only!")]
    )
    upload_label = Label(upload, "Choose File")
    submit = SubmitField("Upload Image")

    def save(self):
        photo = self.upload.data

        if validate_image(photo):
            try:
                filename = photos.save(photo)
                return filename
            except UploadNotAllowed:
                return None

        return None
