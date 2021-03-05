"""
Functions for retrieving and storing the data for individual articles
"""
from pymed import PubMed
import sqlite3, dataset
import os

DATASET_PATH = 'review_speed.db'

def setup_db():
    """
    Creates a sqlite3 db if it doesn't exist
    """
    if not os.path.exists(DATASET_PATH):
        sqlite3.connect(DATASET_PATH)

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
        doi_urls.append('https://doi.org/' + entry.doi)
    return doi_urls

def add_article_to_db(doi_url, publisher, journal, dates):
    """
    Adds article review speed data to the database
    
    Parameters
    ----------
    doi_url: (str) url of the form https://doi.org/XXXX
    publisher: (str) publisher main domain name (e.g. elsevier, tandfonline, etc.)
    dates: (dict) datetime.datetime objs for three events (Received, Accepted, Published)

    Returns
    ----------
    None
    """
    db = dataset.connect(f'sqlite:///{DATASET_PATH}')
    article_data = {'doi_url': doi_url,
                    'journal': journal,
                    'publisher': publisher}
    article_data.update(dates)
    db['Articles'].insert(article_data)