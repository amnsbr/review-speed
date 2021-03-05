"""
Functions for retrieving and storing the data for individual articles
"""
from pymed import PubMed

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