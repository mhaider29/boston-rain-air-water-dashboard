"""


"""
import os
import pandas as pd
import numpy as np
from dask.core import literal
from pandas import read_csv
import xarray as xr
from datetime import date
from typing import Literal

#import data acquisition files
from acquire_data import acquire_wqp_data
from acquire_data import acquire_precip_data
from acquire_data import acquire_air_quality

BASE_PRECIP_URL = "http://psl.noaa.gov/thredds/dodsC/Datasets/cpc_us_precip/RT"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")



def rename_air_water_columns(water_df: pd.DataFrame, air_df: pd.DataFrame):
    wqp_df = water_df.rename(columns= {'Latitude': "lat_wqp", 'Longitude': 'lon_wqp'})
    aq_df = air_df.rename(columns = {"latitude": 'lat_aq', "longitude": 'lon_aq'})
    return wqp_df, aq_df


def add_precip(df: pd.DataFrame,
               precip_da: xr.DataArray, lat_col: str, lon_col: str, date_col: str):
    """
    adds the daily precipitation closest to the lat and lon of the air
    or water quality data point
    df: the dataframe you want to add precipitation values to
    precip_da: a data array with precip values
    lat_col: the label for the latitude column in df
    lon_col: the label for the longitude column in df
    date_col: the label for the date column in df
    returns: the original dataframe with the precipitation values closest to the
    individual latitude and longitude for each row of data in df
    """
    #convert the longitude into a 0-360 value for matching with the precip data
    lon_360 = df[lon_col] % 360
    #ensure that the dates from df are datetime data type
    times = pd.to_datetime(df[date_col])

    # use .sel() to look up precip values from the xarray at specific coordinates
    #dims = 'points' identifies single data points rather than cross products
    # method = 'nearest' matches to the closest lat, lon, and date.
    p = precip_da.sel(
        lat = xr.DataArray(df[lat_col].values, dims='points'),
        lon = xr.DataArray(lon_360.values, dims = 'points'),
        time = xr.DataArray(times.values, dims='points'),
        method = 'nearest'
    )
    #add a new column with the matching precip data to the original df
    df['precip_mm'] = p.values

    return df

def kenmore_all_chars(air_df, water_df):
    kenmore_air = air_df[air_df['neighborhood'] == 'Kenmore Sq']. copy()
    kenmore_water = water_df[water_df['neighborhood'] ==
                             'Fenway-Kenmore'].copy()
    kenmore_air['date'] = pd.to_datetime(kenmore_air['date'])
    kenmore_water['date'] = pd.to_datetime(kenmore_water['date'])
    kenmore_all = pd.merge(kenmore_air, kenmore_water, on='date', how='outer')
    kenmore_clean = kenmore_all.drop(columns=['latitude', 'longitude', 'neighborhood_x', 'Latitude',
                                              'Longitude', 'neighborhood_y'])
    return kenmore_clean



def remove_outliers(df: pd.DataFrame, col: str, lower: float = 0.05, upper: float = 0.95) -> pd.DataFrame:
    """
    Remove outliers from a column using quantile-based filtering.

    :param df: DataFrame to filter
    :param col: Column to filter outliers on
    :param lower: Lower quantile threshold. Defaults to 0.05.
    :param upper: Upper quantile threshold. Defaults to 0.95.
    :return: DataFrame with outliers removed.
    """
    #get the lowest value withing the range specified
    low = df[col].quantile(lower)
    #get the highest value within the range specified
    high = df[col].quantile(upper)
    #return the values between the lowest and highest percentiles
    return df[(df[col] >= low) & (df[col] <= high)]

def wq_pct_change(df: pd.DataFrame,
                   metric: str = 'Turbidity (NTU)',
                   lag: int = 1,
                   min_precip: float = 1,
                  neighborhood: Literal['West End','Back Bay','Allston'] = 'West End'
                   ) -> tuple[pd.DataFrame, str]:
    """
    Add a percent change column representing the change in the metric between
    the day before a precipitation event and lag days after.

    :param df: Dataframe containing the metric column, sorted by date.
    :param metric: The metric column to compute percent change for.
    :param lag: Number of days after the precipitation event to compare to. Defaults to 1.
    :param min_precip: the minimum value of precipitation that should be included
    :param neighborhood: The neighborhood to filter to. Must be one of 'West End', 'Back Bay', or 'Allston'.
    Defaults to 'West End'.
    :return: Dataframe with an additional metric_pct_change column. Defaults to 1
    """

    #get a copy of the data for only the specified neighborhood and sort by the date
    df = (df[df["neighborhood"] == neighborhood]
            .sort_values("date")
            .reset_index(drop=True)
            .copy())

    # get the water quality metric the day before precipitation
    df["metric_before"] = df[metric].shift(1)
    # Get the water quality metric lag number of days after precipitation
    df["metric_after"] = df[metric].shift(-lag)
    #calculate the percent change between the day before and lag days after precipitation
    df["metric_pct_change"] = ((df["metric_after"] - df["metric_before"]) / df["metric_before"]) * 100
    #remove infinite values (when the metric_before is 0 you get infinity in the pct change column)
    df["metric_pct_change"] = df["metric_pct_change"].replace([np.inf, -np.inf], np.nan)
    #get rid of the columns for before or after
    df = df.drop(columns=["metric_before", "metric_after"])


    # return only rows with precipitation values higher than the minimum precipitation
    df = df[(df['precip_mm'] > float(min_precip))]
    # drop rows with na values in the percent change column
    df = df[['date', 'precip_mm', 'metric_pct_change']].dropna(subset=['metric_pct_change'])
    #remove outliers
    df = remove_outliers(df, "metric_pct_change")

    return (df, metric)

def aq_pct_change(df: pd.DataFrame,
                   metric: str = 'pm25 (µg/m³)',
                   lag: int = 1,
                  min_precip: float = 1,
                  neighborhood: Literal['Kenmore Sq','Roxbury','South Boston'] = 'Roxbury'
                   ) -> tuple[pd.DataFrame, str]:
    """
    Compute the percent change in an air quality metric between the day before
    and lag days after a precipitation event for a specific neighborhood.

    :param df: Dataframe containing the metric, precip_mm, and neighborhood columns, sorted by date.
    :param metric: The air quality metric column to compute percent change for. Defaults to 'pm25 (µg/m³)'.
    :param lag: Number of days after the precipitation event to compare to. Defaults to 1.
    :param min_precip: Minimum precipitation in mm to include a row. Defaults to 1.
    :param neighborhood: The neighborhood to filter to. Must be one of 'Kenmore Sq', 'Roxbury', or
                         'South Boston'. Defaults to 'Roxbury'.
    :return: a tuple with the dataframe with date, precip_mm, and metric_pct_change columns and the metric used.
    """

    #sort by the date and neighborhood
    df = (df[df["neighborhood"] == neighborhood]
            .sort_values("date")
            .reset_index(drop=True)
            .copy())

    #get the metrics the day before precipitation events and lag days after
    df["metric_before"] = df[metric].shift(1)
    df["metric_after"] = df[metric].shift(-lag)
    #calculate the percent change between the two days
    df["metric_pct_change"] = ((df["metric_after"] - df["metric_before"]) / df["metric_before"]) * 100
    #replace infinite values wth NA
    df["metric_pct_change"] = df["metric_pct_change"].replace([np.inf, -np.inf], np.nan)
    #drop unneeded columns
    df = df.drop(columns=["metric_before", "metric_after"])

    #keep rows with precipitation greater than the minimum precipitation
    df = df[(df['precip_mm'] > float(min_precip))]
    #drop rows with NA values in the percent change column
    df = df[['date', 'precip_mm', 'metric_pct_change']].dropna(subset=['metric_pct_change'])
    #remove outliers
    df = remove_outliers(df, "metric_pct_change")

    return (df, metric)



def main():
    air_data = acquire_air_quality.acquire()
    water_data = acquire_wqp_data.acquire(start_date='05-01-2016', end_date='05-01-2025')
    precip_data = acquire_precip_data.load_boston_precip(BASE_PRECIP_URL)


    merge_aq_precip = add_precip(air_data, precip_data, lat_col="latitude", lon_col="longitude", date_col='date')
    merge_wqp_precip = add_precip(water_data, precip_data, lat_col="Latitude",lon_col="Longitude",date_col="date")


    print(len(wq_pct_change(merge_wqp_precip)[0]))
    print(len(aq_pct_change(merge_aq_precip)[0]))

    print(type(precip_data))

    kenmore_data = kenmore_all_chars(merge_aq_precip, merge_wqp_precip)
    kenmore_data.to_csv(os.path.join(DATA_DIR, "kenmore_data.csv"))
    return kenmore_data, merge_aq_precip, merge_wqp_precip






if __name__ == "__main__":
    main()