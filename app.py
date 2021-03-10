# -*- coding: utf-8 -*-

# The template is similar to https://github.com/plotly/dash-sample-apps/tree/master/apps/dash-aix360-heart

import dash
import dash_html_components as html
import dash_core_components as dcc
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
from flask_caching import Cache


import datetime

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from entities import orm, db, Publisher, SubjectArea, SubjectCategory, Journal, Article

# Config
STATIC_PLOT = True
SHOW_SCATTER = False
CACHE_TIMEOUT = 24 * 60 * 60 #seconds


# Connect to database
DATASET_PATH = 'database.sqlite'
db.bind(provider='sqlite', filename=DATASET_PATH, create_db=True)
db.generate_mapping(create_tables=True)
# Get available journals list
with orm.db_session:
    journal_options = []
    for journal in Journal.select(lambda j: len(j.articles)>0):
        journal_options.append({'label': journal.abbr_name, 'value': journal.abbr_name})

# App initialization and layout
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server
cache = Cache(server, config={
    'CACHE_TYPE': 'FileSystemCache',
    'CACHE_DIR': 'FlaskCaching'
})

# Define the journal and date selection forms
form_groups = [
    dbc.FormGroup(
        [
            dbc.Label('Journal Abbreviation'), 
            html.Form(autoComplete='off', children=
            [
                dcc.Dropdown(id="journal-abbr-dropdown")
            ])
            
        ]),
    dbc.FormGroup(
        [
            dbc.Label('Date Range'), 
            dcc.DatePickerRange(
                id='date-picker-range',
                min_date_allowed=datetime.date(1970, 1, 1),
                max_date_allowed=datetime.date.today() + datetime.timedelta(365),
                initial_visible_month=datetime.date.today(),
            ),
        ]),

]


def create_summary_cards(articles_df):
    """
    Creates html summary cards for Submit to Accept, Accept to Publish,
    and Submit to Publish duration based on articles_df

    Parameters
    ----------
    artilces_df: (pandas.DataFrame) The review speed data from selected articles

    Returns
    ----------
    cards: (list) of (dbc.Card) htmls
    """
    colors = ['light', 'dark', 'primary']
    inverse_font_colors = [False, True, True]
    #> N of articles card
    cards = [
        dbc.Card(
            [
                html.H2(f"{articles_df.shape[0]} Articles", className="card-title"),
                html.H5(f"{articles_df['published'].min().strftime('%Y %b')} - {articles_df['published'].max().strftime('%Y %b')}", className="card-title"),
                html.Br(className="card-text"),
            ],
            body=True,
            inverse=True,
            color='info')
    ]
    #> Review speed median(IQR) cards
    for idx, var in enumerate(['Submit to Accept', 'Accept to Publish', 'Submit to Publish']):
        card = dbc.Card(
            [
                html.H2(f"{articles_df[var].median()}", className="card-title"),
                html.H5(f"({articles_df[var].quantile(.25)}-{articles_df[var].quantile(.75)})", className="card-title"),
                html.P(var, className="card-text"),
            ],
            body=True,
            inverse=inverse_font_colors[idx],
            color=colors[idx])
        cards.append(card)
    return cards

def plot_histogram(articles_df):
    """
    Plots the histogram for Submit to Accept duration based on articles_df

    Parameters
    ----------
    artilces_df: (pandas.DataFrame) The review speed data from selected articles

    Returns
    ----------
    graph: (dcc.Graph) review speed histogram
    """
    nbins = int((articles_df["Submit to Accept"].max() - articles_df["Submit to Accept"].min()) // 10)
    fig = px.histogram(articles_df, 
                       x="Submit to Accept", 
                       nbins=nbins)
    fig.update_layout(
        xaxis_title="Submit to Accept (days)",
        yaxis_title="Count",
    )
    graph = dcc.Graph(
                    id='histogram',
                    figure=fig,
                    config={
                        'staticPlot': STATIC_PLOT,
                    })
    return graph

# Trend plot
def plot_trend(articles_df):
    """
    Plots the monthly trend of Submit to Accept duration based on articles_df
    
    Parameters
    ----------
    artilces_df: (pandas.DataFrame) The review speed data from selected articles

    Returns
    ----------
    graph: (dcc.Graph) Submit to Accept monthly trend plot
    """
    DOI_BASE = 'https://doi.org/'
    articles_grouped_by_month = articles_df.set_index('published').groupby(pd.Grouper(freq='MS'))
    monthly_trend_median = articles_grouped_by_month['Submit to Accept'].median()
    #> Initialize the figure
    fig = go.Figure()
    #> Add boxplots for each month
    fig.add_trace(go.Box(
        y=articles_df['Submit to Accept'],
        x=articles_df['published'].apply(lambda x: datetime.datetime(x.year, x.month, 1)),
        # .to_period is not an option because plotly doesn't work with pd.Period
        boxpoints=False,
        name='Monthly Boxplot',
        showlegend=SHOW_SCATTER, #show the legend only if scatter is also shown
        hoverinfo='none'
    ))
    #> Add the trend line of medians for each month
    fig.add_trace(go.Scatter(
        name='Median',
        x=monthly_trend_median.index,
        y=monthly_trend_median,
        mode='lines',
        line=dict(color='rgb(31, 119, 180)'),
        showlegend=False,
        hoverinfo='none'
    ))
    #> Add the review speed of individual studies scatter
    if SHOW_SCATTER:
        fig.add_trace(go.Scatter(
            y=articles_df['Submit to Accept'],
            x=articles_df['published'], 
            mode='markers',
            name='Articles',
            text=articles_df['doi'],
            showlegend=True
        ))
    fig.update_layout(
        xaxis_title="Date Published",
        yaxis_title="Submit to Accept (days)",
    )
    #> Set x-axis to be monthly
    fig.update_xaxes(
        dtick="M1",
        tickformat="%b\n%Y")
    graph = dcc.Graph(
        id="graph-trend",
        figure=fig,
        config={
            'staticPlot': STATIC_PLOT,
            }
        )
    return graph

#> App base layout
app.layout = dbc.Container(
    [
        dbc.Row(html.H2('Review Speed Analytics', style={"margin-top": 15})),
        html.Hr(),
        dbc.Row([dbc.Col(form_group) for form_group in form_groups]),
        html.Hr(),
        dbc.Row(id='summary-cards'),
        dbc.Row(html.P('* Median (25th - 75th percentiles) in days'), id="numbers-note", style={"display": "none"}),
        dbc.Row(id='graphs'),
    ],
    fluid=False,
)

#> Dynamic dropdown search callback
@app.callback(
    Output("journal-abbr-dropdown", "options"),
    [Input("journal-abbr-dropdown", "search_value")],
)
def update_options(search_value):
    """
    Callback handling journal name search autocomplete
    """
    if not search_value:
        raise dash.exceptions.PreventUpdate
    return [o for o in journal_options if search_value.lower() in o["label"].lower()]

# > Journal info view callback
@app.callback(
    [Output("summary-cards", "children"), 
     Output("graphs", "children"), 
     Output("numbers-note", "style")],
    Input("journal-abbr-dropdown", "value"),
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date")
)
@cache.memoize(timeout=CACHE_TIMEOUT)
def show_journal_info(journal_abbr, start_date, end_date):
    """
    Callback updating summary cards and graphs based on selected
    journal and dates

    Parameters
    ----------
    journal_abbr: (str) journal abbreviation based on NLM Catalog
    start_date: (datetime.date)
    end_date: (datetime.date)

    Returns
    ---------
    cards: (list) of (dbc.Card) htmls containing number of artciles and median(IQR) review speed
    graphs: (list) of (dcc.Graph) [histogram, trend_graph]
    numbers_note_style: (dict) indicating whether the note about median(IQR) should be visible
    """
    if journal_abbr:
        #> Get articles df for the journal from db
        with orm.db_session:
            journal = Journal.get(abbr_name=journal_abbr)
            articles_df = pd.DataFrame([article.to_dict() for article in journal.articles])
            articles_df['journal']=journal.abbr_name
            for event in ['received', 'accepted', 'published']:
                articles_df[event] = pd.to_datetime(articles_df[event])
        #> Limit to start_date and end_date
        if start_date:
            articles_df = articles_df[articles_df['published'] >= start_date]
        if end_date:
            articles_df = articles_df[articles_df['published'] <= end_date]
        articles_df['Submit to Accept'] = (articles_df['accepted'] - articles_df['received']).dt.days
        articles_df['Accept to Publish'] = (articles_df['published'] - articles_df['accepted']).dt.days
        articles_df['Submit to Publish'] = (articles_df['published'] - articles_df['received']).dt.days
        #> Create summary cards
        if articles_df.shape[0] > 0:
            cards = create_summary_cards(articles_df)
            cards_row_content = [dbc.Col(card) for card in cards]
            #> Plot the graphs
            histogram = plot_histogram(articles_df)
            trend_graph = plot_trend(articles_df)
            graphs = [histogram, trend_graph]
            graphs_row_content = [dbc.Col(graph) for graph in graphs]
            return cards_row_content, graphs_row_content, {'display': 'inline'}
        else:
            return [html.H4("No articles in this time range")], [], {'display': 'none'}
    else:
        return [], [], {'display': 'none'}

if __name__ == '__main__':
    app.run_server(host='localhost', debug=True)
    