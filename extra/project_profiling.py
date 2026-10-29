import os
import pandas as pd
from ydata_profiling import ProfileReport

# finds data/ in the project folder (one level above extra/), so this runs on any computer
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

df = pd.read_csv(os.path.join(PROJECT_ROOT, "data", "air_quality_all.csv"),
                 low_memory=False)
df.info()

profile = ProfileReport(df, title="Air Quality Data Report")
profile.to_file(os.path.join(PROJECT_ROOT, "extra", "air_quality_report.html"))