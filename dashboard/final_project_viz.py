'''
This layer handles creating visualizations for the dashboard.
'''
import sys
import os

import numpy as np
from scipy import stats

# directs searches to the parent (project) directory to deal with subfolders
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

import merge_data
from acquire_data import acquire_precip_data, acquire_wqp_data, acquire_air_quality


def water_quality_bubble_plot(df, metric):
    '''
    Creates a scatter plot of a given water quality metric overlaid over a map. Each point in the plot represents a
    monitoring station, with its size indicating the water quality metric's value at that point.

    :df: Pandas DataFrame containing all water quality data
    :metric: Water quality metric to plot
    :returns: A Plotly scatter map figure showing the spatial distribution of the selected water quality metric
    '''
    df = df.groupby(['Latitude', 'Longitude'])[metric].mean().reset_index().dropna(subset=[metric])
    return px.scatter_map(
        df, lat='Latitude', lon='Longitude', size=metric,
        title=f"{metric} – Spatial Distribution", size_max=40, zoom=12,
        map_style='carto-positron')

def kenmore_triple_timeseries(df: pd.DataFrame,
                               metric1: str,
                               metric2: str,
                               metric3: str,
                               cutoff_year: int = 2025) -> list:
    """
    Build three separate static time series figures showing data up to cutoff_year.
    Called by the dashboard with a Player widget to animate year by year.

    :param df: Kenmore merged dataframe
    :param metric1: Column name for the top panel
    :param metric2: Column name for the middle panel
    :param metric3: Column name for the bottom panel
    :param cutoff_year: Only show data up to and including this year
    :return: List of three Plotly figures, one per metric
    """
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    full_min = df['date'].min()  # add this
    full_max = df['date'].max()  # add this
    df = df[df['date'].dt.year <= cutoff_year]  # filter to cutoff year

    metrics = [metric1, metric2, metric3]
    colors = ['steelblue', 'tomato', 'seagreen']
    figures = []

    for metric, color in zip(metrics, colors):
        plot_df = df.dropna(subset=[metric])
        full_df = pd.to_datetime(df['date'])

        if 'precip' in metric.lower():
            trace = go.Bar(
                x=plot_df['date'], y=plot_df[metric],
                name=metric, marker_color=color, opacity=1.0
            )
        elif plot_df[metric].count() < 500:
            trace = go.Scatter(
                x=plot_df['date'], y=plot_df[metric],
                name=metric, mode='markers',
                marker=dict(color=color, size=6, opacity=0.8)
            )
        else:
            trace = go.Scatter(
                x=plot_df['date'], y=plot_df[metric],
                name=metric, mode='lines',
                line=dict(color=color, width=1.2)
            )

        fig = go.Figure(data=[trace])
        fig.update_layout(
            title=f"{metric} (up to {cutoff_year})",
            height=280,
            showlegend=False,
            plot_bgcolor='white',
            paper_bgcolor='white',
            xaxis=dict(
                title='Date',
                type='date',  # keeps dates on the axis even when a metric has no data yet
                range=[full_min, full_max]
            ),
            yaxis=dict(title=metric)
        )
        fig.update_xaxes(showgrid=True, gridcolor='lightgrey')
        fig.update_yaxes(showgrid=True, gridcolor='lightgrey')
        figures.append(fig)

    return figures

PRECIP_COL = 'precip_mm'
PCT_CHANGE_COL = 'metric_pct_change'

def create_scatterplot(data: pd.DataFrame, metric_label: str, title: str, **kwargs):

    #get keyword arguments
    figure_width = kwargs.get('figure_width', 800)
    figure_height = kwargs.get("figure_height", 400)

    #calculate trendline and r-value
    result = stats.linregress(data[PRECIP_COL], data[PCT_CHANGE_COL])
    x_range = np.linspace(data[PRECIP_COL].min(), data[PRECIP_COL].max(), 100)
    #create empty figure
    fig = go.Figure()

    #add the scatter plot to the empty figure
    fig.add_trace(go.Scatter(
        x=data[PRECIP_COL],
        y=data[PCT_CHANGE_COL],
        mode = 'markers'
    ))

    fig.add_trace(go.Scatter(
        x = x_range,
        y = result.slope*x_range + result.intercept,
        mode = 'lines',
        name = f'trendline (r={result.rvalue:.2f})',
        line = dict(color = 'red', dash='dash')
    ))


    #update figure size, title, and axis titles
    fig.update_layout(
        title = title,
        width = figure_width,
        height = figure_height,
        xaxis_title = 'Precipitation (mm)',
        yaxis_title = f'{metric_label} percent change'
    )


    return fig


def main():
    precip_data = acquire_precip_data.load_boston_precip("http://psl.noaa.gov/thredds/dodsC/Datasets/cpc_us_precip/RT")
    air_data = acquire_air_quality.acquire()
    water_data = acquire_wqp_data.acquire(start_date='05-01-2016', end_date='05-01-2025')

    aq_precip = merge_data.add_precip(air_data, precip_data, lat_col="latitude", lon_col="longitude", date_col='date')
    wqp_precip = merge_data.add_precip(water_data, precip_data, lat_col="Latitude",lon_col="Longitude",date_col="date")

    aq_change, aq_metric = merge_data.aq_pct_change(aq_precip)
    aq_change = merge_data.remove_outliers(aq_change, 'metric_pct_change')

    wqp_change, wqp_metric = merge_data.wq_pct_change(wqp_precip)
    wqp_change = merge_data.remove_outliers(wqp_change,'metric_pct_change')

    create_scatterplot(wqp_change, metric_label= wqp_metric, title = 'pct_change')

if __name__ == "__main__":
    main()