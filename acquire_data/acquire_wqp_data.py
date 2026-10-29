'''
Fetch all water quality results from surface water stations near Boston, MA
using the Water Quality Portal (WQP) REST API.
https://www.waterqualitydata.us/webservices_documentation/
'''

import requests
import pandas as pd
import io
import os

BASE_RESULT_URL = 'https://www.waterqualitydata.us/data/Result/search'

# project folder (one level above acquire_data/), so the cache is found from any directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE_PATH = os.path.join(PROJECT_ROOT, 'data', 'wqp_data.csv')

# Surface water stations in and around Boston
SITE_IDS = [
    'USGS-01103050', 'USGS-01104672', 'USGS-01104680', 'USGS-01104681', 'USGS-01104690', 'USGS-01104700',
    'USGS-01104705', 'USGS-01104710', 'USGS-01104715', '1111REG1-CRBL05', '1111REG1-CRBL06', '1111REG1-CRBL07',
    '1111REG1-CRBL08', '1111REG1-CRBL09', '1111REG1-CRBL10', '1111REG1-CRBL11', '1111REG1-CRBL12', 'CRWA-3BU',
    'CRWA-4LONG', 'CRWA-HAR', 'CRWA-LG', 'CRWA-MB', 'CRWA-SP', 'CRWA-CB', 'CRWA-ND', 'CRWA-SD', 'MWRA_WQX-MWRA-004',
    'MWRA_WQX-MWRA-006', 'MWRA_WQX-MWRA-007', 'MWRA_WQX-MWRA-008', 'MWRA_WQX-MWRA-009', 'MWRA_WQX-MWRA-010',
    'MWRA_WQX-MWRA-011', 'MWRA_WQX-MWRA-145', 'MWRA_WQX-MWRA-166', 'MWRA_WQX-MWRA-206', 'MWRA_WQX-MWRA-210'
]

# site_id: (latitude, longitude)
COORDS_DICT = {
    'USGS-01104672': (42.3673722222222, -71.1177388888889), 'USGS-01104680': (42.3541666666667, -71.1144444444444),
    'USGS-01104681': (42.3537083778954, -71.1106078526668), 'USGS-01104690': (42.3542083333333, -71.0873555555555),
    'USGS-01104700': (42.3538166666667, -71.08385), 'USGS-01104705': (42.36222222222222, -71.0786111111111),
    'USGS-01104710': (42.3659306204141, -71.0700513497836), 'USGS-01104715': (42.36888888888889, -71.06166666666667),
    '1111REG1-CRBL05': (42.3537286, -71.1132058), '1111REG1-CRBL06': (42.3525053, -71.1063100),
    '1111REG1-CRBL07': (42.3527908, -71.0877256), '1111REG1-CRBL08': (42.3536047, -71.0837806),
    '1111REG1-CRBL09': (42.3603664, -71.0804347), '1111REG1-CRBL10': (42.3604850, -71.0735061),
    '1111REG1-CRBL11': (42.3652144, -71.0729822), '1111REG1-CRBL12': (42.3685325, -71.0664253),
    'CRWA-3BU': (42.3526000000, -71.1112000000), 'CRWA-4LONG': (42.3611000000, -71.0758000000),
    'CRWA-HAR': (42.3546300000, -71.0913800000), 'CRWA-LG': (42.3543500000, -71.0811600000),
    'CRWA-MB': (42.3546400000, -71.1147400000), 'CRWA-SP': (42.3583700000, -71.0878300000),
    'CRWA-CB': (42.3590100000, -71.0731000000), 'CRWA-ND': (42.3693500000, -71.0618400000),
    'CRWA-SD': (42.3568700000, -71.0758900000), 'MWRA_WQX-MWRA-004': (42.3629480000, -71.1169010000),
    'MWRA_WQX-MWRA-006': (42.3525000000, -71.1085000000), 'MWRA_WQX-MWRA-007': (42.3549986000, -71.0968930000),
    'MWRA_WQX-MWRA-008': (42.3545000000, -71.0895000000), 'MWRA_WQX-MWRA-009': (42.3575000000, -71.0764440000),
    'MWRA_WQX-MWRA-010': (42.3638510000, -71.0748092000), 'MWRA_WQX-MWRA-011': (42.3682841000, -71.0670750000),
    'MWRA_WQX-MWRA-145': (42.3519299000, -71.0920070000), 'MWRA_WQX-MWRA-166': (42.3661774000, -71.0702014000),
    'MWRA_WQX-MWRA-206': (42.3526780000, -71.1106940000), 'MWRA_WQX-MWRA-210': (42.3647220000, -71.0758330000)
}

# site id: neighborhood
NB_DICT = {
    'USGS-01104672': 'Allston',
    'USGS-01104680': 'Fenway-Kenmore',
    'USGS-01104681': 'Fenway-Kenmore',
    'USGS-01104690': 'Back Bay',
    'USGS-01104700': 'Back Bay',
    'USGS-01104705': 'West End',
    'USGS-01104710': 'West End',
    'USGS-01104715': 'West End',
    '1111REG1-CRBL05': 'Fenway-Kenmore',
    '1111REG1-CRBL06': 'Fenway-Kenmore',
    '1111REG1-CRBL07': 'Back Bay',
    '1111REG1-CRBL08': 'Back Bay',
    '1111REG1-CRBL09': 'Back Bay',
    '1111REG1-CRBL10': 'West End',
    '1111REG1-CRBL11': 'West End',
    '1111REG1-CRBL12': 'West End',
    'CRWA-3BU': 'Fenway-Kenmore',
    'CRWA-4LONG': 'West End',
    'CRWA-HAR': 'Back Bay',
    'CRWA-LG': 'Back Bay',
    'CRWA-MB': 'Fenway-Kenmore',
    'CRWA-SP': 'Back Bay',
    'CRWA-CB': 'West End',
    'CRWA-ND': 'West End',
    'CRWA-SD': 'Back Bay',
    'MWRA_WQX-MWRA-004': 'Allston',
    'MWRA_WQX-MWRA-006': 'Fenway–Kenmore',
    'MWRA_WQX-MWRA-007': 'Back Bay',
    'MWRA_WQX-MWRA-008': 'Back Bay',
    'MWRA_WQX-MWRA-009': 'Back Bay',
    'MWRA_WQX-MWRA-010': 'West End',
    'MWRA_WQX-MWRA-011': 'West End',
    'MWRA_WQX-MWRA-145': 'Back Bay',
    'MWRA_WQX-MWRA-166': 'West End',
    'MWRA_WQX-MWRA-206': 'Fenway–Kenmore',
    'MWRA_WQX-MWRA-210': 'West End'
}

# columns from the API request that we actually need
KEEP_COLS = [
    'MonitoringLocationIdentifier',
    'ActivityStartDate',
    'CharacteristicName',
    'ResultMeasureValue',
    'ResultMeasure/MeasureUnitCode',
    'ResultDetectionConditionText'
]

CRITICAL_COLS = [
    'MonitoringLocationIdentifier',
    'ActivityStartDate',
    'CharacteristicName',
    'ResultMeasureValue',
    'ResultMeasure/MeasureUnitCode'
]

def fetch_results(start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
    '''
    Fetch all water quality results for the given station IDs.
    Uses POST to avoid URL length limits with many site IDs.

    :param SITE_IDS:   list of WQP MonitoringLocationIdentifier strings
    :param start_date: earliest sample date, MM-DD-YYYY (optional)
    :param end_date:   latest  sample date, MM-DD-YYYY (optional)
    :return: dataframe containing all results for the given station IDs and date range, with only the columns we care
    about or need for cleaning.
    '''
    # run request for data from specified stations between specified dates
    payload: dict = {"siteid": SITE_IDS}
    if start_date:
        payload['startDateLo'] = start_date
    if end_date:
        payload['startDateHi'] = end_date

    url = f'{BASE_RESULT_URL}?mimeType=csv&zip=no&sorted=no'

    resp = requests.post(url, json=payload, timeout=180)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text), low_memory=False)

    # only keep the necessary cols
    available = [c for c in KEEP_COLS if c in df.columns]
    return df[available]

def clean_results(df: pd.DataFrame) -> pd.DataFrame:
    '''
    Clean the API dataframe by filling in missing values, dropping unnecessary columns.

    :param df: resulting dataframe from API call
    :return: clean dataframe
    '''
    # if there are multiple rows with the same site, date, time, and characteristic (this is like a primary key),
    # average the measurement values
    key_cols = [
        "MonitoringLocationIdentifier",
        "ActivityStartDate",
        "CharacteristicName"
    ]

    available_keys = [c for c in key_cols if c in df.columns]

    # save non-key columns separately or else pandas will drop them in the groupby
    non_key_cols = [c for c in df.columns if c not in available_keys and c != 'ResultMeasureValue']

    df = (
        df.groupby(available_keys, as_index=False)
        .agg({'ResultMeasureValue': 'mean', **{c: 'first' for c in non_key_cols}})
    )

    # if measurement value is missing but the condition column has something in it (not detected or below detection
    # threshold, fill measurement column with 0
    mask = (df['ResultMeasureValue'].isna() & df['ResultDetectionConditionText'].notna())
    df.loc[mask, 'ResultMeasureValue'] = 0

    # drop the result condition column after using it in the previous step
    df = df.drop(columns=['ResultDetectionConditionText'])

    # if critical column is mising, remove the row
    df = df.dropna(subset=[c for c in CRITICAL_COLS if c in df.columns])

    # rename date column for easier merging later
    df = df.rename(columns={'ActivityStartDate': 'date'})

    # convert to datetime
    df['date'] = pd.to_datetime(df['date'])

    return df

def map_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    '''
    Adds latitude and longitude columns by mapping site IDs to coordinates.

    :param df: cleaned dataframe
    :return: dataframe with latitude and longitude columns
    '''
    # create new columns by mapping site ID to coordinates
    df['Latitude'], df['Longitude'] = zip(*df['MonitoringLocationIdentifier'].map(COORDS_DICT))

    return df

def map_neighborhoods(df: pd.DataFrame) -> pd.DataFrame:
    '''
    Adds neighborhood columns by mapping site IDs to neighborhood names.

    :param df: cleaned dataframe
    :return: dataframe with neighborhood names
    '''
    df['neighborhood'] = df['MonitoringLocationIdentifier'].map(NB_DICT)
    return df

def pivot_characteristics(df):
    '''
    Converts the structure of the dataframe to a pivot table-like structure.
    This allows for easier plotting later on.

    :param df: cleaned dataframe
    :return: pivoted dataframe with one row per date, lat, lon, and neighborhood and
    columns for each characteristic with the mean value
    '''
    #get all of the units for each measurement
    units = df.groupby("CharacteristicName")["ResultMeasure/MeasureUnitCode"].first()

    #group by the date, lat, lon, and characteristic name, take the mean if there are multiple
    #values and then convert them into individual columns
    pivoted = (df.groupby(['date','Latitude','Longitude','neighborhood', 'CharacteristicName'])['ResultMeasureValue']
               .mean()
               .unstack('CharacteristicName')
               .reset_index()
               )
    #creates a dictionary with original characteristics as keys and the characteristic and
    #units as the values. columns = then matches the columns to the keys and replaces with the value
    pivoted = pivoted.rename(columns={char: f"{char} ({units[char]})" for char in units.index})

    return pivoted

def acquire(start_date: str | None = None,
                  end_date: str | None = None) -> pd.DataFrame:
    '''
    Main pipeline to acquire water quality data from the WQP API, clean it, and add coordinates and neighborhood names.
    '''
    file_path = FILE_PATH
    if os.path.exists(file_path):
        final_df = pd.read_csv(file_path)
    else:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        results = fetch_results(start_date='05-01-2016', end_date='05-01-2025')
        cleaned = clean_results(results)

        add_coords = map_coordinates(cleaned)
        add_nbs = map_neighborhoods(add_coords)
        final_df = pivot_characteristics(add_nbs)
        final_df.to_csv(file_path)
    return final_df

if __name__ == '__main__':
    acquire(start_date='05-01-2016', end_date='05-01-2025')