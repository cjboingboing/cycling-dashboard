import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from dotenv import load_dotenv
load_dotenv()

from src.ingestion.strava import StravaClient
# rest of the script...
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / '.env')
print("CWD:", os.getcwd())
print("env exists:", os.path.exists('.env'))

print("ID:", os.getenv("STRAVA_CLIENT_ID"))
print("SECRET:", os.getenv("STRAVA_CLIENT_SECRET"))
print("REFRESH:", os.getenv("STRAVA_REFRESH_TOKEN"))

from dotenv import load_dotenv
load_dotenv()

from src.ingestion.strava import StravaClient

client = StravaClient()
activities = client.load_activities(max_activities=10)
print(activities[["date", "name", "type", "duration_s", "avg_power_w"]].tail(10))
activities = client.load_activities(max_activities=500)
print(f"Total activities: {len(activities)}")
print(f"Date range: {activities['date'].min()} to {activities['date'].max()}")