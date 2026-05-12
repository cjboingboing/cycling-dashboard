"""
strava.py
---------
Fetch activity data from the Strava API using OAuth2.

First-time setup:
1. Create an app at https://www.strava.com/settings/api
2. Set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in .env
3. Run get_refresh_token() once in a browser to complete OAuth
4. Paste the resulting refresh token into .env as STRAVA_REFRESH_TOKEN

Subsequent runs use the refresh token automatically.

Usage:
    from src.ingestion.strava import StravaClient
    client = StravaClient()
    activities_df = client.load_activities(max_activities=200)
"""

import os
import time
from datetime import datetime

import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE  = "https://www.strava.com/api/v3"


class StravaClient:
    def __init__(self):
        self.client_id     = os.getenv("STRAVA_CLIENT_ID")
        self.client_secret = os.getenv("STRAVA_CLIENT_SECRET")
        self.refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")
        self._access_token = None
        self._token_expiry = 0

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _get_access_token(self) -> str:
        """Refresh the access token if expired."""
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token

        resp = requests.post(STRAVA_TOKEN_URL, data={
            "client_id":     self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type":    "refresh_token",
        })
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._token_expiry = data["expires_at"]
        return self._access_token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_access_token()}"}

    # ------------------------------------------------------------------
    # Activities
    # ------------------------------------------------------------------

    def load_activities(
        self,
        max_activities: int = 500,
        after: int | None = None,
    ) -> pd.DataFrame:
        """
        Fetch activities from Strava.

        Parameters
        ----------
        max_activities : upper bound on rows returned (safety cap)
        after          : Unix timestamp — only return activities strictly after
                         this time. Pass int(date.timestamp()) to do an
                         incremental sync from a known cutoff.
        """
        activities = self._paginate_activities(max_activities, after=after)
        if not activities:
            return pd.DataFrame()
        records = [self._parse_activity(a) for a in activities]
        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"]).dt.tz_convert(None).dt.normalize()
        return df.sort_values("date").reset_index(drop=True)

    def _paginate_activities(
        self,
        max_activities: int,
        after: int | None = None,
    ) -> list[dict]:
        results = []
        page = 1
        per_page = min(100, max_activities)

        while len(results) < max_activities:
            params: dict = {"page": page, "per_page": per_page}
            if after is not None:
                params["after"] = after

            resp = requests.get(
                f"{STRAVA_API_BASE}/athlete/activities",
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            results.extend(batch)
            if len(batch) < per_page:
                break  # last page — no point making another request
            page += 1
            time.sleep(0.5)   # gentle on rate limits

        return results[:max_activities]

    def _parse_activity(self, a: dict) -> dict:
        return {
            "activity_id": a.get("id"),
            "date":        pd.to_datetime(a.get("start_date_local")),
            "name":        a.get("name"),
            "type":        a.get("sport_type", "").lower(),
            "duration_s":  a.get("moving_time"),
            "distance_m":  a.get("distance"),
            "elevation_m": a.get("total_elevation_gain"),
            "avg_power_w": a.get("average_watts"),
            "np_w":        a.get("weighted_average_watts"),
            # Strava doesn't expose TSS directly — computed in processing
            "tss":         None,
            "avg_hr":      a.get("average_heartrate"),
            "calories":    a.get("calories"),
            "source":      "strava",
        }

    # ------------------------------------------------------------------
    # Power streams (for power curve)
    # ------------------------------------------------------------------

    def get_power_stream(self, activity_id: int) -> pd.Series | None:
        """
        Fetch second-by-second power data for a single activity.
        Returns a pd.Series of watts indexed by second, or None if unavailable.
        """
        resp = requests.get(
            f"{STRAVA_API_BASE}/activities/{activity_id}/streams",
            headers=self._headers(),
            params={"keys": "watts", "key_by_type": "true"},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()

        if "watts" not in data:
            return None

        return pd.Series(data["watts"]["data"], name="watts")

    # ------------------------------------------------------------------
    # First-time OAuth helper (run interactively once)
    # ------------------------------------------------------------------

    @staticmethod
    def get_auth_url(client_id: str) -> str:
        """Print the URL the user needs to visit to authorise the app."""
        return (
            f"https://www.strava.com/oauth/authorize"
            f"?client_id={client_id}"
            f"&response_type=code"
            f"&redirect_uri=http://localhost"
            f"&approval_prompt=force"
            f"&scope=activity:read_all"
        )

    @staticmethod
    def exchange_code_for_token(client_id: str, client_secret: str, code: str) -> dict:
        """Exchange the auth code (from redirect URL) for tokens."""
        resp = requests.post(STRAVA_TOKEN_URL, data={
            "client_id":     client_id,
            "client_secret": client_secret,
            "code":          code,
            "grant_type":    "authorization_code",
        })
        resp.raise_for_status()
        return resp.json()
