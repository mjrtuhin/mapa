import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

SELENIUM_HEADLESS = False
SELENIUM_TIMEOUT = 30
REQUEST_DELAY_MIN = 2
REQUEST_DELAY_MAX = 5

GRID_ZOOM_LEVEL = 15
MAX_RESULTS_PER_GRID = 120

DEFAULT_REVIEW_LIMIT = 50

SUCCESS_RATING_THRESHOLD = 4.1
SUCCESS_REVIEW_THRESHOLD = 100

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
