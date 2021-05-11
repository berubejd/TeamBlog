from datetime import datetime

from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from itsdangerous import TimedJSONWebSignatureSerializer

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(
        db.String(255), unique=True, index=True, nullable=False, server_default=""
    )
    displayname = db.Column(db.String(256), unique=True, nullable=False)
    active = db.Column("is_active", db.Boolean(), nullable=False, server_default="1")

    # Activity tracking.
    sign_in_count = db.Column(db.Integer, nullable=False, default=0)
    current_sign_in_on = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    current_sign_in_ip = db.Column(db.String(45))
    last_sign_in_on = db.Column(db.DateTime)
    last_sign_in_ip = db.Column(db.String(45))

    def get_id(self):
        return self.id

    def is_active(self):
        return self.active

    def update_activity_tracking(self, ip_address):
        self.sign_in_count += 1

        self.last_sign_in_on = self.current_sign_in_on
        self.last_sign_in_ip = self.current_sign_in_ip

        self.current_sign_in_on = datetime.utcnow()
        self.current_sign_in_ip = ip_address

        return self.save()

    def save(self):
        db.session.add(self)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

        return self

    def delete(self):
        db.session.delete(self)
        return db.session.commit()

    @classmethod
    def deserialize_token(cls, token):
        private_key = TimedJSONWebSignatureSerializer(current_app.config["SECRET_KEY"])
        try:
            decoded_payload = private_key.loads(token)

            return User.query.filter(
                User.email == decoded_payload.get("user_email")
            ).first()
        except Exception:
            return None

    def serialize_token(self, expiration=3600):
        private_key = current_app.config["SECRET_KEY"]

        serializer = TimedJSONWebSignatureSerializer(private_key, expiration)
        return serializer.dumps({"user_email": self.email}).decode("utf-8")

    def __repr__(self):
        return self.username
