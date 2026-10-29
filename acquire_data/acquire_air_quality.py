"""
Acquire air quality data from OpenAQ API
Produces: data/air_quality_all.csv

- 3 Boston neighborhoods: Roxbury, Kenmore Sq, South Boston
- 8 pollutant sensors (co, no, no2, nox, o3, pm10, pm25, so2)
- May 2016 to May 2025
- Columns: date, neighborhood, sensor, value, units
"""

import requests       # sends HTTP requests to the OpenAQ API
import pandas as pd   # dataframe operations
import dotenv         # reads the .env file into environment variables
import os             # accesses environment variables and file paths
from time import sleep  # pauses execution to avoid hitting API rate limits

# reads the .env file so os.environ.get() can find OPENAQ_KEY
# .env is in .gitignore so the key is never committed to the repo
dotenv.load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

# pulls the API key from the environment variable set in .env
# stored in .env instead of hardcoded so it's never accidentally committed
API_KEY = os.environ.get("OPENAQ_KEY")

# every request to the OpenAQ API needs this header to authenticate
HEADERS = {"X-API-Key": API_KEY}

# base URL — all API endpoints are built by appending to this
BASE_URL = "https://api.openaq.org/v3"

# gets the absolute path of the project folder (one level above acquire_data/)
# used to build OUTPUT_PATH so the CSV saves to the right place
# regardless of what directory the script is run from
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# full path to the output CSV — joins BASE_DIR with data/air_quality_all.csv
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "air_quality_all.csv")

# ============================================================================
# DATE RANGE
# ============================================================================

# ISO 8601 format strings used directly as API query parameters
DATE_FROM  = "2016-05-12T00:00:00Z"   # earliest date to fetch from the API
DATE_TO    = "2025-05-31T23:59:59Z"   # latest date to fetch from the API

# pandas Timestamps used for filtering the dataframe after fetching
START_DATE = pd.Timestamp("2016-05-12")  # inclusive lower bound
END_DATE   = pd.Timestamp("2025-05-31")  # inclusive upper bound

# maps neighborhood names to OpenAQ location IDs
# IDs were found by manually querying the OpenAQ API for Boston sensors
LOCATIONS = {
    "Roxbury":      448,   # OpenAQ location ID for Roxbury sensor
    "Kenmore Sq":   521,   # OpenAQ location ID for Kenmore Sq sensor
    "South Boston": 688,   # OpenAQ location ID for South Boston sensor
}

# South Boston's API coordinates are wrong — it returns Texas (33.19, -97.19)
# instead of Boston (42.33, -71.05). We discovered this when plotting sensor
# locations and one dot appeared in Texas. This dict stores the correct
# coordinates to override the bad API values before saving.
COORD_OVERRIDES = {
    "South Boston": (42.33343, -71.04949),  # correct Boston coordinates
}

# ============================================================================
# API HELPERS
# ============================================================================

def get_sensors(location_id):
    """Get all sensors at a location."""

    # builds the endpoint URL for this specific location's sensors
    url = f"{BASE_URL}/locations/{location_id}/sensors"

    # sends GET request with our API key in the header
    resp = requests.get(url, headers=HEADERS)

    # raises an exception if the response was 4xx or 5xx
    # stops the pipeline early with a clear error instead of silently failing
    resp.raise_for_status()

    # parses the JSON response and returns just the results list
    return resp.json()["results"]


def get_daily_measurements(sensor_id, limit=1000):
    """
    Get daily measurements for a sensor within a date range.
    Uses pagination to retrieve all results.
    """

    # endpoint for daily measurements for this specific sensor
    url = f"{BASE_URL}/sensors/{sensor_id}/days"

    dataset = []  # accumulates results across all pages
    page = 1      # starts at page 1

    while True:   # keeps looping until we break out

        # query parameters sent with the request
        params = {
            "limit": limit,              # max results per page (API max is 1000)
            "page": page,                # which page we're requesting
            "datetime_from": DATE_FROM,  # start of our date range
            "datetime_to": DATE_TO,      # end of our date range
            "order_by": "datetime",      # sort results by date
            "sort_order": "asc",         # oldest first
        }

        # sends the GET request with all query parameters
        resp = requests.get(url, headers=HEADERS, params=params)
        print(f"  Sensor {sensor_id} page {page}: status {resp.status_code}")

        if resp.status_code == 200:  # success
            # extracts the results list from the JSON response
            results = resp.json().get("results", [])

            # adds this page's results to our running total
            dataset += results

            # if we got fewer results than the limit, this was the last page
            # so we break out of the loop
            if len(results) < limit:
                break

            # otherwise increment page and keep going
            page += 1

        elif resp.status_code == 429:  # rate limited
            # API told us we're making too many requests — wait 10s and retry
            print("  Rate limited — waiting 10s...")
            sleep(10)  # pauses execution for 10 seconds before retrying

        else:  # any other error (404, 500, etc.)
            # something went wrong — stop trying for this sensor
            break

    return dataset  # returns the full list of measurements across all pages


def get_location_coords(location_id):
    """Get latitude and longitude for a location."""

    # endpoint for this specific location's details
    url = f"{BASE_URL}/locations/{location_id}"

    # sends GET request with authentication header
    resp = requests.get(url, headers=HEADERS)

    # raises an exception if the request failed
    resp.raise_for_status()

    # parses JSON and gets the first result (there's only one per location)
    data = resp.json()["results"][0]

    # extracts lat and lon from the nested coordinates dictionary
    lat = data["coordinates"]["latitude"]
    lon = data["coordinates"]["longitude"]

    return lat, lon  # returns as a tuple

# ============================================================================
# DATAFRAME CONVERSION
# ============================================================================

def convert_to_dataframe(measurements, neighborhood, sensor_name, units, lat, lon):
    """
    Convert a list of daily measurements into rows.
    """

    records = []  # will hold one dictionary per measurement

    for m in measurements:  # loops through each measurement dict from the API
        records.append({
            # datetimeFrom is the start of the measurement period
            # "local" gives the local timezone string instead of UTC
            "date":         m["period"]["datetimeFrom"]["local"],

            # neighborhood name we assigned (not from the API)
            "neighborhood": neighborhood,

            # pollutant name e.g. 'pm25', 'no2'
            "sensor":       sensor_name,

            # the actual measurement reading
            "value":        m["value"],

            # units string e.g. 'µg/m³', 'ppm'
            "units":        units,

            # coordinates — same for every row from this location
            "latitude":     lat,
            "longitude":    lon,
        })

    # converts the list of dicts into a pandas DataFrame
    return pd.DataFrame(records)

# ============================================================================
# DATA CLEANING
# ============================================================================

def clean_air_quality(df):
    """
    Clean the OpenAQ air quality dataframe.
    """

    # drops any row that has a null in ANY column
    # nulls come from sensor malfunctions where the sensor reported a period
    # but had no actual value — we can't impute these so we drop them
    df = df.dropna()

    # removes exact duplicate rows
    # the API occasionally returns the same reading twice across paginated requests
    df = df.drop_duplicates()

    # removes rows where the pollutant value is negative
    # negative concentrations are physically impossible — a negative PM2.5
    # means the sensor malfunctioned, so we drop these rather than keep
    # bad data that would skew averages
    df = df[df["value"] >= 0]

    # casts value to float to ensure consistent numeric dtype for math operations
    df["value"] = df["value"].astype(float)

    # casts lat/lon to float for xarray coordinate lookups in merge_data.py
    df["latitude"] = df["latitude"].astype(float)
    df["longitude"] = df["longitude"].astype(float)

    return df

# ============================================================================
# DATE NORMALIZATION
# ============================================================================

def normalize_air_quality_dates(df):
    """
    Normalize dates so all three neighborhoods are on the same timezone
    and time format before merging.
    """

    # step 1: parse the date string as UTC first, then convert to Eastern time
    # utc=True forces pandas to treat all strings as UTC before converting
    # this handles daylight saving time correctly since offsets vary by season
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert("America/New_York")

    # step 2: normalize strips the time component and sets everything to midnight
    # South Boston reports at 01:00 while others report at 00:00
    # normalizing to midnight makes all three neighborhoods comparable
    df["date"] = df["date"].dt.normalize()

    # step 3: remove timezone info entirely
    # pandas merge and xarray .sel() both require timezone-naive datetimes
    # tz_localize(None) removes the timezone without changing the time value
    df["date"] = df["date"].dt.tz_localize(None)

    # step 4: filter to our study period
    # trims any data outside START_DATE to END_DATE that slipped through
    # the API date parameters
    df = df[(df["date"] >= START_DATE) & (df["date"] <= END_DATE)]

    return df

# ============================================================================
# DATE FIXING AND PIVOTING
# ============================================================================

def fix_aq_dates(aq_df):
    """
    Convert datetime objects to plain date objects and sort ascending.
    """

    # .dt.date strips the time component entirely, leaving plain date objects
    # merge_data.py works with plain dates not full Timestamps so this
    # prevents type mismatch errors during the merge
    aq_df["date"] = pd.to_datetime(aq_df["date"]).dt.date

    # sorts the dataframe chronologically — needed before pivoting
    aq_sorted = aq_df.sort_values(by="date")

    return aq_sorted


def pivot_aq(aq_df):
    """
    Pivot air quality data from long format to wide format.
    Each sensor becomes its own column, e.g. 'pm25 (µg/m³)'.
    """

    # gets the units string for each sensor (e.g. pm25 -> µg/m³)
    # used later to build column names like 'pm25 (µg/m³)'
    units = aq_df.groupby("sensor")["units"].first()

    pivoted = (
        aq_df
        # groups by date, location, neighborhood, and sensor
        # if multiple readings exist for the same combination, we average them
        .groupby(["date", "latitude", "longitude", "neighborhood", "sensor"])["value"]
        .mean()  # average multiple readings for the same sensor/date/location

        # unstack moves the 'sensor' index level into column headers
        # so each unique sensor name becomes its own column
        .unstack("sensor")

        # resets the multi-level index back to a flat dataframe
        .reset_index()
    )

    # renames columns from e.g. 'pm25' to 'pm25 (µg/m³)'
    # including units in the column name makes plot axis labels self-documenting
    pivoted = pivoted.rename(
        columns={char: f"{char} ({units[char]})" for char in units.index}
    )

    return pivoted

# ============================================================================
# MAIN PIPELINE
# ============================================================================

def acquire(reload=False):
    """
    Main entry point. Either loads from cache or fetches fresh from the API.
    """

    # if the CSV already exists and reload is False, skip the API entirely
    # the API calls take several minutes and have rate limits
    # historical data from 2016-2025 won't change so caching is safe
    if not reload and os.path.exists(OUTPUT_PATH):
        print(f"Data already exists at {OUTPUT_PATH}, loading from file...")
        # parse_dates ensures the date column comes back as datetime not string
        df = pd.read_csv(OUTPUT_PATH, parse_dates=["date"])
        return df

    all_dfs = []  # accumulates one dataframe per sensor across all neighborhoods

    # loops through each neighborhood and its OpenAQ location ID
    for neighborhood, loc_id in LOCATIONS.items():
        print(f"\n=== {neighborhood} (location {loc_id}) ===")

        # use manually corrected coordinates if available (South Boston)
        # otherwise fetch from the API
        if neighborhood in COORD_OVERRIDES:
            lat, lon = COORD_OVERRIDES[neighborhood]  # use our correct coordinates
        else:
            lat, lon = get_location_coords(loc_id)  # fetch from API

        # gets the list of all sensors at this location
        sensors = get_sensors(loc_id)
        print(f"Found {len(sensors)} sensors")

        # loops through each sensor at this location
        for sensor in sensors:
            sid         = sensor["id"]             # unique sensor ID for API calls
            param       = sensor["parameter"]      # parameter dict with name and units
            sensor_name = param["name"]            # pollutant name e.g. 'pm25'
            units       = param.get("units", "")  # units string, empty string if missing

            print(f"  Fetching {sensor_name} ({units})...")

            # fetches all daily measurements for this sensor (handles pagination)
            measurements = get_daily_measurements(sid)
            print(f"  Got {len(measurements)} daily readings")

            # only convert and append if we got data back
            # some sensors have no readings in our date range
            if measurements:
                df = convert_to_dataframe(measurements, neighborhood,
                                          sensor_name, units, lat, lon)
                all_dfs.append(df)  # adds this sensor's data to our list

            # small pause between sensor requests to avoid hitting rate limits
            sleep(0.5)

    # combines all individual sensor dataframes into one big dataframe
    # ignore_index=True resets the row index so there are no duplicates
    final_df = pd.concat(all_dfs, ignore_index=True)

    # runs the full cleaning and reshaping pipeline in order
    final_df = normalize_air_quality_dates(final_df)  # fix timezones and normalize to midnight
    final_df = clean_air_quality(final_df)             # drop nulls, dupes, negatives
    final_df = fix_aq_dates(final_df)                  # convert to plain dates and sort
    final_df = pivot_aq(final_df)                      # reshape to wide format
    final_df = final_df.sort_values(
        ["neighborhood", "date"]).reset_index(drop=True)  # sort by neighborhood then date

    # creates the data/ directory if it doesn't exist yet
    os.makedirs("data", exist_ok=True)

    # saves to CSV without the pandas row index column
    final_df.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved {len(final_df)} rows to {OUTPUT_PATH}")
    print(final_df.head(10))  # preview the first 10 rows

    return final_df


if __name__ == "__main__":
    acquire()  # runs the full pipeline when this file is executed directly