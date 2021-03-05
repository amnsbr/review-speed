"""
Functions for retrieving and storing the data for individual articles
"""
from pymed import PubMed
import sqlite3, dataset
import os
import scraper

DATASET_PATH = 'review_speed.db'

def setup_db():
    """
    Creates a sqlite3 db if it doesn't exist
    """
    if not os.path.exists(DATASET_PATH):
        sqlite3.connect(DATASET_PATH)

def add_article_to_db(doi_url, publisher, journal_abbr, dates, db=None):
    """
    Adds article review speed data to the database
    
    Parameters
    ----------
    doi_url: (str) url of the form https://doi.org/XXXX
    publisher: (str) publisher main domain name (e.g. elsevier, tandfonline, etc.)
    dates: (dict) datetime.datetime objs for three events (Received, Accepted, Published)
    db: (dataset.database.Database) connected db potentially passed from fetch_journal_recent_articles_data

    Returns
    ----------
    None
    """
    if not db:
        db = dataset.connect(f'sqlite:///{DATASET_PATH}')
    article_data = {'doi_url': doi_url,
                    'journal_abbr': journal_abbr,
                    'publisher': publisher}
    article_data.update(dates)
    db['Articles'].insert(article_data)

def get_journal_recent_doi_urls(journal_abbr, max_results=50):
    """
    Uses PubMed to get the latest articles of a journal based on its name

    Parameters
    ----------
    journal_abbr: (str) journal abbreviation according to NLM catalog
    max_results: (int) number of recent articles to retrieve

    Returns
    ----------
    doi_urls: (list) a list of doi_urls
    """
    pubmed = PubMed()
    doi_urls = []
    entries = pubmed.query(f"{journal_abbr}[jour]", max_results=max_results)
    for entry in entries:
        # > a quick fix for a bug in pymed (0.8.9), which sometimes returns a multiline list of dois
        # for a entry. And the first one is the real one
        doi = entry.doi.split('\n')[0]
        doi_urls.append('https://doi.org/' + doi)
    return doi_urls

def fetch_journal_recent_articles_data(journal_abbr, max_results=50, verbosity='full'):
    """
    Adds review dates of recent journal articles to the database
    Parameters
    ----------
    journal_abbr: (str) journal abbreviation according to NLM catalog
    max_results: (int) number of recent articles to retrieve
    verbosity: (str or None) 'full' will print all dois, 'summary' prints the counter every 5 articles, None prints nothing

    Returns
    ----------
    None
    """
    db = dataset.connect(f'sqlite:///{DATASET_PATH}')
    doi_urls = get_journal_recent_doi_urls(journal_abbr, max_results)
    counter = 0
    for doi_url in doi_urls:
        if verbosity=='full':
            print(doi_url)
        #> Check if doi_url is already in the database
        if db['Articles'].count(doi_url=doi_url) > 0:
            if verbosity=='full':
                print('Already in the table')
        else:
            #> Get the dates and publisher, and if dates is non-empty, save the article data in db
            dates, publisher = scraper.get_dates(doi_url)
            if any([v is not None for v in dates.values()]): #> the operation has succeeded
                add_article_to_db(doi_url, publisher, journal_abbr, dates, db=db)
        counter+=1
        if (counter%5==0) and (verbosity=='summary'):
            print(counter)