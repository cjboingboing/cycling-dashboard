from src.ingestion.strava import StravaClient
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from dotenv import load_dotenv

client = StravaClient()
activities = client.load_activities(max_activities=500)
print(f"Total activities: {len(activities)}")
print(f"Date range: {activities['date'].min()} to {activities['date'].max()}")