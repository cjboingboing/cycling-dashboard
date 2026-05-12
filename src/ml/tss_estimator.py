import joblib
import pandas as pd
from pathlib import Path

MODEL_PATH = Path(__file__).parent / 'tss_model.joblib'

class TSSEstimator:
    def __init__(self):
        self.model = joblib.load(MODEL_PATH)
        self.features = ['duration_s', 'elevation_m']
    
    def predict(self, activities_df: pd.DataFrame) -> pd.DataFrame:
        df = activities_df.copy()
        
        # Only predict where TSS is missing but features are available
        needs_estimate = df['tss'].isna() & df[self.features].notna().all(axis=1)
        
        if needs_estimate.sum() == 0:
            print("No rows need TSS estimation")
            return df
        
        df.loc[needs_estimate, 'tss'] = self.model.predict(
            df.loc[needs_estimate, self.features]
        )
        print(f"Estimated TSS for {needs_estimate.sum()} rides")
        return df