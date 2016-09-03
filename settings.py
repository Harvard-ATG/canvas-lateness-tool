import os
from os.path import join, dirname
from dotenv import load_dotenv

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

OAUTH_TOKEN = os.environ.get("OAUTH_TOKEN")
CANVAS_API_URL = os.environ.get("CANVAS_API_URL")
