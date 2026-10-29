import pandas as pd
from netCDF4 import Dataset, num2date
import numpy as np
import os
from datetime import date
import xarray as xr
from time import sleep

BASE_URL = "http://psl.noaa.gov/thredds/dodsC/Datasets/cpc_us_precip/RT"
# project folder (one level above acquire_data/), so the cache is found from any directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(PROJECT_ROOT, "data", "boston_precip.nc")


def get_boston_slices(base: str,
                      year: int =2016
                      ) -> tuple:
    """
    gets array index slices and coordinate values for the Boston area

    opens one year's data just long enough to get the latitudes and longitudes before closing it.
    The lists can be reused across all years in the dataset as the grid is static.

    :param base: Base OPeNDAP URL for the NOAA CPC precipitation dataset.
    :param year: Year of the file to use for determining grid slices. Defaults to 2016.

    :return: Tuple of lat_slice, lon_slice, boston_lat, boston_lon. The slices are for indexing
    the grid arrays and boston lat and lon are the corresponding coordinate value arrays.
    """
    #open the dataset
    ds = Dataset(f"{base}/precip.V1.0.{year}.nc")
    #create variables with all the latitude and longitude values
    lat = ds.variables['lat'][:]
    lon = ds.variables['lon'][:]
    #close the dataset
    ds.close()
    #get the positions in the array where the latitudes and longitudes are close to boston
    boston_lats = np.where((lat >= 42.0) & (lat <= 42.5))[0]
    boston_lons = np.where((lon >= 288.75) & (lon <= 289.25))[0]
    #create a slice of the first and last values in the latitude and longitude lists
    #used for slicing the full data arrays
    lat_slice = slice(boston_lats[0], boston_lats[-1] + 1)
    lon_slice = slice(boston_lons[0], boston_lons[-1] + 1)
    #use the slices to get the actual latitude and longitude values
    boston_lat = lat[lat_slice]
    boston_lon = lon[lon_slice]

    return lat_slice, lon_slice, boston_lat, boston_lon

def load_boston_precip(base: str,
                       start_yr:int =2016,
                       end_yr: int =2025,
                       reload: bool=False,
                       cache: str = CACHE
                       )-> xr.DataArray:
    """
    Load Boston-area daily precipitation data from NOAA OPeNDAP or local cache.

    On first run or when reload = True, fetches the data year by year and concatenates into a
    single array, filters to the date range, and saves a netCDF file in the local cache.

    :param base: Base OPeNDAP URL for the NOAA CPC precipitation dataset.
    :param start_yr: First year to fetch. Defaults to 2016.
    :param end_yr: Last year to fetch. Defaults to 2025.
    :param reload: If True, re-fetch from remote even if cache exists.
    Defaults to False.

    :return: xarray DataArray with dimensions (time, lat, lon), where time covers START_DATE
     through END_DATE, lat and lon are the Boston grid coordinates (lon in 0-360 format), and
     values are daily precipitation in mm.

    """
    #the path to save the data too
    if not reload and os.path.exists(cache):
        return xr.open_dataarray(cache)

    os.makedirs(os.path.dirname(cache), exist_ok=True)

    all_precip = []
    all_dates = []

    lat_slice, lon_slice, boston_lat, boston_lon = get_boston_slices(base)


    for year in range(start_yr, end_yr + 1):
        ds = Dataset(f"{base}/precip.V1.0.{year}.nc")

        time_var = ds.variables['time']
        dates = [date(d.year, d.month, d.day) for d in num2date(time_var[:], units=time_var.units)]
        all_dates.extend(dates)

        precip = ds.variables['precip'][:, lat_slice, lon_slice]
        all_precip.append(precip)
        ds.close()
        print(f"{year} done, max={precip.max():.2f}")
        sleep(10)

    data = np.ma.concatenate(all_precip, axis=0).filled(np.nan)
    dates = np.array(all_dates)
    mask = (dates >= date(start_yr, 5, 12)) & (dates < date(end_yr, 5, 1))
    dates = pd.to_datetime(dates[mask]).normalize()

    data_array = xr.DataArray(
        data[mask],
        dims = ['time','lat','lon'],
        coords = {'time': dates, 'lat': boston_lat, 'lon':boston_lon}

    )
    data_array.to_netcdf(cache)

    return data_array




def main():

    data = load_boston_precip(base=BASE_URL, reload=True)


if __name__ == "__main__":
    main()