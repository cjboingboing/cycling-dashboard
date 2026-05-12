import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from src.processing.pmc import fill_missing_tss

SEED = 42
FTP  = 333

# Load ground truth data
activities = pd.read_parquet('data/processed/activities.parquet')
activities = fill_missing_tss(activities, ftp=FTP)

# Only rides with power-derived TSS
power_rides = activities[activities['tss'].notna()]
X = power_rides[['duration_s', 'elevation_m']].dropna()
y = power_rides.loc[X.index, 'tss']

# Train on all data
rf = RandomForestRegressor(n_estimators=100, random_state=SEED)
rf.fit(X, y)

# Save
joblib.dump(rf, Path(__file__).parent / 'tss_model.joblib')
print(f"Model trained on {len(X)} rides and saved.")
