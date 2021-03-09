"""
Functions for retrieving and storing the data for individual articles
"""
from pymed import PubMed
import sqlite3, dataset
import requests
import tldextract
import xml.etree.ElementTree as ET 
import os
import scraper
from entities import orm, db, Publisher, Journal, Article

# Connect to database
DATASET_PATH = 'database.sqlite'
db.bind(provider='sqlite', filename=DATASET_PATH, create_db=True)
db.generate_mapping(create_tables=True)

@orm.db_session
def fetch_journal_info_from_nlmcatalog(issn):
    """
    Fetch the journal and publisher info based on issn and add them to the database

    Parameters
    ----------
    issn: (str) Journal's ISSN

    Returns
    ---------
    journal: (entities.Journal)
    """
    if Journal.get(issn=issn):
        print("Journal already in db")
        return Journal.get(issn=issn)
    #> Search in NLM Catalog using ISSN
    search_url = f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=nlmcatalog&term=%22{issn}%22[ISSN]'
    search_res_xml = requests.get(search_url, headers=scraper.REQUESTS_AGENT_HEADERS).text
    search_res_root = ET.fromstring(search_res_xml)
    #> Check if the search has any results
    if not search_res_root.findall('IdList'):
        print("Does not exist")
        return None, None
    #> Get the NLM Catalogy ID and fetch its info xml
    nlmcatalog_id = search_res_root.findall('IdList')[0].getchildren()[0].text
    journal_url = f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nlmcatalog&rettype=xml&id={nlmcatalog_id}'
    journal_res_xml = requests.get(journal_url, headers=scraper.REQUESTS_AGENT_HEADERS).text
    #> Parse the XML and extract fullname and abbr name
    journal_res_root = ET.fromstring(journal_res_xml)
    full_name = journal_res_root.find('NLMCatalogRecord').find('TitleMain').find('Title').text
    full_name = full_name.rstrip('.') # Remove the trailing "." from the name of some journals
    abbr_name = journal_res_root.find('NLMCatalogRecord').find('MedlineTA').text
    #> Get the journal and pmc url (if exists)
    pmc_url = journal_url = ''
    for ELocation in journal_res_root.find('NLMCatalogRecord').find('ELocationList').findall('ELocation'):
        ELocation_url = ELocation.find('ELocationID').text
        if ELocation_url.startswith('https://www.ncbi.nlm.nih.gov/pmc/journals'):
            pmc_url = ELocation_url
        else:
            journal_url = ELocation_url
    #> Get the publisher url and domain from journal url
    journal_url_extract = tldextract.extract(journal_url)
    publisher_url = journal_url_extract.fqdn
    publisher_domain = journal_url_extract.domain
    #> Check if publisher is supported
    publisher_supported = publisher_domain in scraper.SUPPORTED_DOMAINS
    #> Create Publisher (if does not exist) and Journal database instances
    publisher = Publisher.get(domain=publisher_domain)
    if not publisher:
        publisher = Publisher(
            domain=publisher_domain, 
            url=publisher_url, 
            supported=publisher_supported)
    journal = Journal(
        full_name=full_name, 
        abbr_name=abbr_name, 
        issn=issn,
        nlmcatalog_id=nlmcatalog_id,
        pmc_url=pmc_url,
        publisher=publisher)
    #> Save the database
    orm.commit()
    return journal

def fetch_journal_recent_articles_data(journal_abbr, max_results=50, verbosity='full'):
    """
    Uses PubMed to get the latest articles of a journal based on its name

    Parameters
    ----------
    journal_abbr: (str) journal abbreviation according to NLM catalog
    max_results: (int) number of recent articles to retrieve. 0 will get all the articles
    verbosity: (str or None) 'full' will print all dois, 'summary' prints the counter every 5 articles, None prints nothing

    Returns
    ----------
    articles: (list) a list of entities.Article items
    """
    pubmed = PubMed()
    entries = pubmed.query(f"{journal_abbr}[jour]", max_results=max_results)
    articles = []
    counter = 0
    for entry in entries:
        # > a quick fix for a bug in pymed (0.8.9), which sometimes returns a multiline list of dois
        # for a entry. And the first one is the real one
        doi = entry.doi.split('\n')[0]
        if verbosity=='full':
            print(doi)
        article = Article.get(doi=doi)
        if not article:
            journal=Journal.get(abbr_name=journal_abbr)
            dates = scraper.get_dates(doi, journal.publisher.domain)
            if any([v is not None for v in dates.values()]): #> the operation has succeeded
                article = Article(
                    doi=doi,
                    title=entry.title,
                    authors=[f"{a['lastname']} {a['initials']}" for a in entry.authors],
                    journal=journal,
                    received=dates['Received'],
                    accepted=dates['Accepted'],
                    published=dates['Published']
                )
                orm.commit()
        articles.append(article)
        counter+=1
        if (counter%5==0) and (verbosity=='summary'):
            print(counter)

    return articles