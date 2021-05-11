import os
import sys

from dotenv import load_dotenv

load_dotenv()

path = os.getenv("APP_PATH")
if path not in sys.path:
    sys.path.insert(0, path)

from teamblog import app as application

if __name__ == "__main__":
    debug = os.getenv("DEBUG") == "True"
    application.app.run(debug=debug)
