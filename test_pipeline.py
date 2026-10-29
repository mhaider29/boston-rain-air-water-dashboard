import os
import xarray as xr
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock
import merge_data
from acquire_data import acquire_air_quality

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


# ============================================================================
# WQP DATA
# ============================================================================

@pytest.fixture(scope="module")
def df():
    return pd.read_csv(os.path.join(DATA_DIR, "wqp_data.csv"), low_memory=False)


class TestCoordinates:
    def test_latitude_is_float(self, df):
        assert pd.api.types.is_float_dtype(df["Latitude"]), (
            "Latitude column is not float dtype"
        )

    def test_longitude_is_float(self, df):
        assert pd.api.types.is_float_dtype(df["Longitude"]), (
            "Longitude column is not float dtype"
        )

    def test_no_null_latitudes(self, df):
        assert df["Latitude"].notna().all(), (
            f"{df['Latitude'].isna().sum()} null value(s) found in Latitude"
        )

    def test_no_null_longitudes(self, df):
        assert df["Longitude"].notna().all(), (
            f"{df['Longitude'].isna().sum()} null value(s) found in Longitude"
        )

    def test_latitude_in_valid_range(self, df):
        out_of_range = df[(df["Latitude"] < -90) | (df["Latitude"] > 90)]
        assert out_of_range.empty, (
            f"{len(out_of_range)} Latitude value(s) outside [-90, 90]"
        )

    def test_longitude_in_valid_range(self, df):
        out_of_range = df[(df["Longitude"] < -180) | (df["Longitude"] > 180)]
        assert out_of_range.empty, (
            f"{len(out_of_range)} Longitude value(s) outside [-180, 180]"
        )


class TestDates:
    def test_activity_start_date_parseable(self, df):
        try:
            parsed = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="raise")
        except Exception as e:
            pytest.fail(f"date could not be parsed as YYYY-MM-DD dates: {e}")

    def test_activity_start_date_no_nulls(self, df):
        assert df["date"].notna().all(), (
            f"{df['date'].isna().sum()} null value(s) found in date"
        )

    def test_activity_start_date_no_future_dates(self, df):
        parsed = pd.to_datetime(df["date"], errors="coerce")
        future = parsed[parsed > pd.Timestamp.today()]
        assert future.empty, (
            f"{len(future)} date value(s) are in the future"
        )

class TestDuplicates:
    def test_no_duplicate_rows(self, df):
        n_dupes = df.duplicated().sum()
        assert n_dupes == 0, f"{n_dupes} duplicate row(s) found"

    def test_no_duplicate_measurements(self, df):
        key_cols = ["date", "Latitude", "Longitude"]
        available = [c for c in key_cols if c in df.columns]
        n_dupes = df.duplicated(subset=available).sum()
        assert n_dupes == 0, f"{n_dupes} duplicate measurement(s) found"


# ============================================================================
# AIR QUALITY DATA
# ============================================================================

@pytest.fixture(scope="module")
def aq_df():
    df = pd.read_csv(os.path.join(DATA_DIR, "air_quality_all.csv"))
    return df.dropna(subset=["date", "neighborhood"])


class TestAirQualityCoordinates:
    def test_latitude_is_float(self, aq_df):
        assert pd.api.types.is_float_dtype(aq_df["latitude"]), (
            "latitude column is not float dtype"
        )

    def test_longitude_is_float(self, aq_df):
        assert pd.api.types.is_float_dtype(aq_df["longitude"]), (
            "longitude column is not float dtype"
        )

    def test_latitude_in_boston_range(self, aq_df):
        out_of_range = aq_df[(aq_df["latitude"] < 42.2) | (aq_df["latitude"] > 42.5)]
        assert out_of_range.empty, (
            f"{len(out_of_range)} latitude value(s) outside Boston range"
        )

    def test_longitude_in_boston_range(self, aq_df):
        out_of_range = aq_df[(aq_df["longitude"] < -71.2) | (aq_df["longitude"] > -70.9)]
        assert out_of_range.empty, (
            f"{len(out_of_range)} longitude value(s) outside Boston range"
        )


class TestAirQualityValues:
    def test_no_negative_values(self, aq_df):
        sensor_cols = [c for c in aq_df.columns if "(" in c]
        negative = (aq_df[sensor_cols] < 0).any().any()
        assert not negative, "negative pollutant value(s) found"

    def test_no_null_values(self, aq_df):
        sensor_cols = [c for c in aq_df.columns if "(" in c]
        assert not aq_df[sensor_cols].isnull().all().all(), (
            "all values are null in sensor columns"
        )

    def test_valid_sensors(self, aq_df):
        valid_sensors = {"co", "no", "no2", "nox", "o3", "pm10", "pm25", "so2"}
        col_sensors = {c.split(" ")[0] for c in aq_df.columns if "(" in c}
        assert col_sensors.issubset(valid_sensors), (
            f"Unexpected sensor(s): {col_sensors - valid_sensors}"
        )

    def test_valid_neighborhoods(self, aq_df):
        valid = {"Roxbury", "Kenmore Sq", "South Boston"}
        invalid = aq_df[~aq_df["neighborhood"].isin(valid)]
        assert invalid.empty, (
            f"Unexpected neighborhood(s): {invalid['neighborhood'].unique()}"
        )


class TestAirQualityDates:
    def test_no_null_dates(self, aq_df):
        assert aq_df["date"].notna().all(), (
            f"{aq_df['date'].isna().sum()} null date(s) found"
        )

    def test_no_future_dates(self, aq_df):
        parsed = pd.to_datetime(aq_df["date"], utc=True, errors="coerce")
        future = parsed[parsed > pd.Timestamp.today(tz="UTC")]
        assert future.empty, (
            f"{len(future)} date(s) are in the future"
        )


class TestAirQualityDuplicates:
    def test_no_duplicate_rows(self, aq_df):
        n_dupes = aq_df.duplicated().sum()
        assert n_dupes == 0, f"{n_dupes} duplicate row(s) found"



# ============================================================================
# PRECIPITATION DATA
# ============================================================================

@pytest.fixture(scope="module")
def precip_data():
    return xr.open_dataarray(os.path.join(DATA_DIR, 'boston_precip.nc'))

class TestPrecipCoordinates:
    def test_latitude_in_boston_range(self, precip_data):
        lats = precip_data.lat.values
        out_of_range = lats[(lats < 41.0) | (lats > 43.5)]
        assert len(out_of_range) == 0, (f"{len(out_of_range)} latitude(s) outside Boston range")

    def test_longitude_in_boston_range(self, precip_data):
        lons = precip_data.lon.values
        out_of_range = lons[(lons < 287.5) | (lons>290.5)]
        assert len(out_of_range)== 0, f"{len(out_of_range)} longitude(s) outside Boston range"

class TestPrecipDates:
    def test_no_duplicate_dates(self, precip_data):
        dates = precip_data.time.values
        n_dupes = len(dates) - len(np.unique(dates))
        assert n_dupes == 0, f"{n_dupes} duplicate date(s) found"

    def test_date_range(self, precip_data):
        dates = pd.to_datetime(precip_data.time.values)
        out_of_range = dates[(dates < "2016-05-01") | (dates > "2025-05-01")]
        assert len(out_of_range) == 0, f"{len(out_of_range)} date(s) out of expected range"

class TestPrecipValues:
    def test_no_negative_precip_values(self, precip_data):
        precips = precip_data.values.flatten()
        negative_precips = precips[precips < 0]
        assert len(negative_precips) == 0, f"{len(negative_precips)} negative precipitation value(s) found"


    def test_no_all_nan_days(self, precip_data):
        daily_nan = np.all(np.isnan(precip_data.values), axis = (1,2))
        assert not np.any(daily_nan), f"{daily_nan.sum()} day(s) with all NaN values"



# ============================================================================
# MERGED DATA
# ============================================================================

"""
Test suite for merge_data.py
Covers: fix_aq_dates, add_precip, rename_air_water_columns, and kenmore_all_chars
"""

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_air_df():
    """Raw air quality dataframe mimicking acquire_air_quality.acquire() output."""
    return pd.DataFrame({
        "date": ["2021-06-01 00:00:00-04:00", "2021-06-01 00:00:00-04:00",
                 "2021-06-02 00:00:00-04:00", "2021-06-03 00:00:00-04:00"],
        "neighborhood": ["Kenmore Sq", "Roxbury", "Kenmore Sq", "Kenmore Sq"],
        "sensor": ["pm25", "pm25", "pm25", "pm25"],
        "value": [10.0, 12.0, 8.0, 6.0],
        "units": ["µg/m³", "µg/m³", "µg/m³", "µg/m³"],
        "latitude": [42.3489, 42.3144, 42.3489, 42.3489],
        "longitude": [-71.0977, -71.0955, -71.0977, -71.0977],
    })


@pytest.fixture
def sample_water_df():
    """Raw water quality dataframe mimicking wqp_data.csv."""
    return pd.DataFrame({
        "date": pd.to_datetime(["2021-06-01", "2021-06-01", "2021-06-02"]),
        "neighborhood": ["Fenway-Kenmore", "Fenway-Kenmore", "Fenway-Kenmore"],
        "CharacteristicName": ["Nitrate", "pH", "Nitrate"],
        "ResultMeasureValue": [0.5, 7.2, 0.6],
        "ResultMeasure/MeasureUnitCode": ["mg/l", "None", "mg/l"],
        "Latitude": [42.349, 42.349, 42.349],
        "Longitude": [-71.098, -71.098, -71.098],
    })


@pytest.fixture
def pivoted_air_df():
    """Pre-pivoted air quality dataframe with precip for kenmore merge tests."""
    return pd.DataFrame({
        "date": pd.to_datetime(["2021-06-01", "2021-06-02"]),
        "latitude": [42.3489, 42.3489],
        "longitude": [-71.0977, -71.0977],
        "neighborhood": ["Kenmore Sq", "Kenmore Sq"],
        "pm25 (µg/m³)": [10.0, 8.0],
        "precip_mm": [2.5, 1.0],
    })


@pytest.fixture
def pivoted_water_df():
    """Pre-pivoted water quality dataframe with precip for kenmore merge tests."""
    return pd.DataFrame({
        "date": pd.to_datetime(["2021-06-01", "2021-06-02"]),
        "Latitude": [42.349, 42.349],
        "Longitude": [-71.098, -71.098],
        "neighborhood": ["Fenway-Kenmore", "Fenway-Kenmore"],
        "Nitrate (mg/l)": [0.5, 0.6],
        "precip_mm": [2.5, 1.0],
    })


# ============================================================================
# 1. fix_aq_dates
# ============================================================================

def test_fix_aq_dates_converts_to_plain_date(sample_air_df):
    """fix_aq_dates should strip timezone and convert to plain date objects."""
    result = acquire_air_quality.fix_aq_dates(sample_air_df)
    first_val = result["date"].iloc[0]
    assert not isinstance(first_val, pd.Timestamp), \
        "date should be a plain date object, not a Timestamp"


def test_fix_aq_dates_sorts_ascending(sample_air_df):
    """fix_aq_dates should sort rows by date ascending."""
    shuffled = sample_air_df.sample(frac=1, random_state=42).reset_index(drop=True)
    result = acquire_air_quality.fix_aq_dates(shuffled)
    dates = list(result["date"])
    assert dates == sorted(dates), "dates should be sorted in ascending order"


# ============================================================================
# 2. rename_air_water_columns
# ============================================================================

def test_rename_air_water_columns_renames_correctly(sample_air_df, sample_water_df):
    """rename_air_water_columns should rename lat/lon columns with source suffixes."""
    wqp_df, aq_df = merge_data.rename_air_water_columns(sample_water_df, sample_air_df)
    assert "lat_wqp" in wqp_df.columns, "water df should have lat_wqp column"
    assert "lon_wqp" in wqp_df.columns, "water df should have lon_wqp column"
    assert "lat_aq" in aq_df.columns, "air df should have lat_aq column"
    assert "lon_aq" in aq_df.columns, "air df should have lon_aq column"


def test_rename_air_water_columns_drops_original_names(sample_air_df, sample_water_df):
    """rename_air_water_columns should remove original latitude/longitude column names."""
    wqp_df, aq_df = merge_data.rename_air_water_columns(sample_water_df, sample_air_df)
    assert "Latitude" not in wqp_df.columns, "Latitude should be renamed in water df"
    assert "latitude" not in aq_df.columns, "latitude should be renamed in air df"


# ============================================================================
# 3. add_precip
# ============================================================================

def test_add_precip_adds_precip_mm_column():
    """add_precip should add a precip_mm column to the dataframe."""
    df = pd.DataFrame({
        "date": pd.to_datetime(["2021-06-01"]),
        "latitude": [42.35],
        "longitude": [-71.10],
    })
    mock_da = MagicMock()
    mock_da.sel.return_value.values = np.array([3.5])
    result = merge_data.add_precip(df, mock_da, lat_col="latitude",
                                   lon_col="longitude", date_col="date")
    assert "precip_mm" in result.columns, "precip_mm column should be added"


def test_add_precip_correct_value():
    """add_precip should assign the correct precip value from the mock data array."""
    df = pd.DataFrame({
        "date": pd.to_datetime(["2021-06-01"]),
        "latitude": [42.35],
        "longitude": [-71.10],
    })
    mock_da = MagicMock()
    mock_da.sel.return_value.values = np.array([3.5])
    result = merge_data.add_precip(df, mock_da, lat_col="latitude",
                                   lon_col="longitude", date_col="date")
    assert result["precip_mm"].iloc[0] == 3.5, "precip_mm value should match mock"


def test_add_precip_converts_longitude_to_360():
    """add_precip should convert longitude to 0-360 range before lookup."""
    df = pd.DataFrame({
        "date": pd.to_datetime(["2021-06-01"]),
        "latitude": [42.35],
        "longitude": [-71.10],
    })
    mock_da = MagicMock()
    mock_da.sel.return_value.values = np.array([1.0])
    merge_data.add_precip(df, mock_da, lat_col="latitude",
                          lon_col="longitude", date_col="date")
    call_kwargs = mock_da.sel.call_args[1]
    lon_passed = call_kwargs["lon"].values[0]
    assert lon_passed == pytest.approx(-71.10 % 360), \
        "longitude should be converted to 0-360 before xarray lookup"


# ============================================================================
# 4. kenmore_all_chars
# ============================================================================

def test_kenmore_all_chars_excludes_non_kenmore(pivoted_air_df, pivoted_water_df):
    """kenmore_all_chars should exclude non-Kenmore neighborhoods from air data."""
    air_with_roxbury = pd.concat([
        pivoted_air_df,
        pd.DataFrame({
            "date": pd.to_datetime(["2021-06-01"]),
            "latitude": [42.3144],
            "longitude": [-71.0955],
            "neighborhood": ["Roxbury"],
            "pm25 (µg/m³)": [15.0],
            "precip_mm": [2.5],
        })
    ], ignore_index=True)
    result = merge_data.kenmore_all_chars(air_with_roxbury, pivoted_water_df)
    assert "Roxbury" not in result.values, \
        "Roxbury rows should be excluded from kenmore merge"


def test_kenmore_all_chars_drops_redundant_columns(pivoted_air_df, pivoted_water_df):
    """kenmore_all_chars should drop lat/lon/neighborhood columns after merge."""
    result = merge_data.kenmore_all_chars(pivoted_air_df, pivoted_water_df)
    for col in ["latitude", "longitude", "neighborhood_x", "neighborhood_y",
                "Latitude", "Longitude"]:
        assert col not in result.columns, f"{col} should be dropped after kenmore merge"


def test_kenmore_all_chars_outer_merge_preserves_rows(pivoted_air_df, pivoted_water_df):
    """Outer merge should preserve all dates from both air and water dataframes."""
    result = merge_data.kenmore_all_chars(pivoted_air_df, pivoted_water_df)
    assert len(result) >= max(len(pivoted_air_df), len(pivoted_water_df)), \
        "outer merge should not drop rows that exist in only one dataframe"


def test_kenmore_all_chars_only_fenway_kenmore_water(pivoted_air_df, pivoted_water_df):
    """kenmore_all_chars should only include Fenway-Kenmore water rows."""
    water_with_extra = pd.concat([
        pivoted_water_df,
        pd.DataFrame({
            "date": pd.to_datetime(["2021-06-01"]),
            "Latitude": [42.36],
            "Longitude": [-71.06],
            "neighborhood": ["Back Bay"],
            "Nitrate (mg/l)": [0.9],
            "precip_mm": [2.5],
        })
    ], ignore_index=True)
    result = merge_data.kenmore_all_chars(pivoted_air_df, water_with_extra)
    assert "Back Bay" not in result.values, \
        "Back Bay water rows should be excluded from kenmore merge"