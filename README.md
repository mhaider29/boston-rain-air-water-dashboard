# Boston Rain, Air & Water Quality Dashboard

How does rain affect air and water quality in Boston? This project pulls nine years of data (May 2016 – May 2025) from three public sources — NOAA precipitation, OpenAQ air quality, and the Water Quality Portal — merges them, and explores the results in an interactive Panel dashboard.

**Team project** for DS3500 (Advanced Programming with Data), Northeastern University, Spring 2026, built with Hannah Rabold and Calvin Vasicek.

## My contributions

- **Air quality pipeline** (`acquire_data/acquire_air_quality.py`): fetches daily readings for 8 pollutants across 3 Boston neighborhoods from the OpenAQ API, handles rate limits, cleans the data (timezones, negative values, incorrect API coordinates), and caches it locally
- **Kenmore time-series visualization**: an interactive 3-panel chart comparing precipitation, air, and water metrics, with an animated year player and speed selector
- **Dashboard structure and layout** (`dashboard/final_project_dashboard.py`)
- **Tests** for the air quality data and pipeline fixtures (`test_pipeline.py`)
- **Docker setup** and project organization (`Dockerfile`, `requirements.txt`, folder structure)

Calvin built the precipitation acquisition, the percent-change analysis, and the precipitation-influence visualizations. Hannah built the water quality pipeline, the water quality map, and finalized the Docker setup.

## Dashboard

The dashboard has three tabs:

1. **Kenmore Time Series** — compare any three metrics over time in Fenway-Kenmore, the only neighborhood with air, water, *and* precipitation data
2. **Water Quality Map** — water quality readings at monitoring stations along the Charles River
3. **Precip Influence** — how air and water quality change in the days after rain

## How to run

Requires Python 3.11+.

```bash
pip install -r requirements.txt
python dashboard/final_project_dashboard.py
```

Then open http://localhost:5006 in your browser.

The cleaned data is already included in `data/`, so **no API key is needed** to run the dashboard. To re-download air quality data yourself, copy `.env.example` to `.env` and add your own free [OpenAQ](https://openaq.org) key.

**With Docker:**

```bash
docker build -t boston-dashboard .
docker run -p 5006:5006 boston-dashboard
```

**Run the tests:**

```bash
pip install pytest
pytest
```

## Project structure

```
acquire_data/     download + clean each data source (air, water, precipitation)
merge_data.py     joins the three sources and computes percent change after rain
dashboard/        Panel dashboard and Plotly visualizations
data/             cached, cleaned data used by the dashboard
extra/            data profiling script
test_pipeline.py  pytest tests for all three datasets
```

## Data sources

### 1. NOAA CPC Unified Gauge-Based Analysis of Daily Precipitation

**Dataset overview:**
Precipitation data was sourced from the NOAA CPC Unified Gauge-Based Analysis via the NOAA Physical Sciences Laboratory OPeNDAP server. The full dataset spans 20.125°N–49.875°N, 230.125°E–304.875°E at 0.25° resolution.

**How it's acquired:**
`acquire_precip_data.py` downloads data from the NOAA OPeNDAP server and caches it as `data/boston_precip.nc`. Later runs load the cached file unless `reload=True` is passed.

**Cleaning decisions:**
Data was subset to a 2x2 grid centered on Boston, MA (42.125°N–42.375°N, 288.875°E–289.125°E) and filtered to May 12, 2016 through April 30, 2025 to align with the other datasets. Masked values representing missing or ocean grid cells were replaced with NaN. Dates were converted from cftime objects to pandas datetime for compatibility with the other datasets.

**Known issues:**
Missing data in the CPC dataset is flagged with a value of -9.96921e+36f, which is stored as a masked value in the NetCDF file and replaced with NaN during processing. Because the dataset uses 0.25° x 0.25° grid cells rather than point measurements, precipitation values may not perfectly represent conditions at specific station locations. Longitude is stored in 0–360° format rather than the standard -180° to 180° convention, so station longitudes from the water and air quality datasets were converted before matching to the nearest grid cell.

### 2. Water Quality Portal (National Water Quality Monitoring Council)

**Dataset overview:**
Water quality data was sourced from the WQP Web Services API, which provides sample data from water quality monitoring stations around the country.

**How it's acquired:**
`acquire_wqp_data.py` downloads data for monitoring stations on the Charles River in Boston for May 2016 to May 2025 and caches it as `data/wqp_data.csv`.

**Cleaning decisions:**
Originally, each row contained a single metric (such as water depth) taken at a station on a certain day and time. Rows missing a station identifier, date, or metric type were dropped. If a metric was measured multiple times in one day at the same station, the measurements were averaged, since the analysis works at a daily level. If a metric was missing but labeled as below the detection threshold, it was set to 0. Geographic coordinates and neighborhoods were mapped to station IDs. The data was then pivoted so each row is a unique date and location, with one column per metric.

**Known issues:**
The data only covers stations on the Charles River, which limits comparisons with air quality data because many Boston neighborhoods do not border the Charles.

### 3. OpenAQ Air Quality Data

**Dataset overview:**
Air quality data was sourced from the OpenAQ API v3. Daily measurements were collected for 3 Boston neighborhoods (Roxbury, Kenmore Sq, and South Boston) across up to 8 pollutant sensors (co, no, no2, nox, o3, pm10, pm25, so2). South Boston data spans May 12, 2016 through May 30, 2025. Kenmore Sq and Roxbury data spans June 8, 2016 through May 30, 2025.

**How it's acquired:**
`acquire_air_quality.py` fetches data from the OpenAQ API (requires an API key in `.env`) and caches it as `data/air_quality_all.csv`. Later runs load the cached file unless `reload=True` is passed.

**Cleaning decisions:**
Rows with missing values were dropped to remove sensor malfunction records. Duplicate rows were removed. Rows with negative pollutant values were dropped, since negative concentrations are physically impossible. Dates were converted to America/New_York time, normalized to midnight, and stripped of timezone info for compatibility with the other datasets. Data was filtered to May 12, 2016 through May 30, 2025. South Boston coordinates were overridden because the API returns incorrect Texas coordinates (33.1944°N, -97.1933°W) instead of the correct Boston location (42.333°N, -71.049°W).

**Known issues:**
Kenmore Sq and Roxbury sensors have no data before June 8, 2016, so the dataset does not start on a uniform date across neighborhoods. South Boston timestamps are recorded at 01:00 rather than midnight, which was resolved by normalizing all timestamps. The API occasionally returns rate-limit errors (HTTP 429), which are handled with a 10-second retry delay.

## Merging the data

`merge_data.py` combines the three sources into analysis-ready dataframes.

`add_precip()` joins daily precipitation to any dataframe by looking up the nearest NOAA grid cell by latitude, longitude, and date (converting longitude from [-180, 180] to [0, 360] to match NOAA's format) and adds a `precip_mm` column.

Fenway-Kenmore is the only neighborhood with air quality, water quality, *and* precipitation data, so it serves as a case study for how rain affects both air and water in a single area. The datasets were combined with an outer merge on date. This keeps every date from each source: the data is collected at different intervals, and rain affects environmental quality for several days afterward, so keeping only overlapping dates would throw away useful information.
