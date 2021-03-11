"""
Functions for retrieving and storing the data for individual articles
"""
from pymed import PubMed
import requests
from bs4 import BeautifulSoup
import tldextract
import xml.etree.ElementTree as ET 
import pandas as pd
import os, time, datetime

import scraper
from entities import orm, db, Publisher, BroadSubjectTerm, Journal, Article

SCIMAGOJR_BASE = 'https://www.scimagojr.com/journalrank.php'
DATASET_PATH = 'data/database.sqlite'

# Connect to database
# if not os.path.exists(DATASET_PATH):
db.bind(provider='sqlite', filename=DATASET_PATH, create_db=True)
db.generate_mapping(create_tables=True)

def search_nlmcatalog(term, retmax=100000):
    #> Search in NLM Catalog using ISSN
    search_url = f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=nlmcatalog&retmax={retmax}&term={term}'
    search_succeeded = False
    retries = 0
    while (retries < 10) and (not search_succeeded):
        try:
            search_res_xml = requests.get(search_url, headers=scraper.REQUESTS_AGENT_HEADERS).text
            search_res_root = ET.fromstring(search_res_xml)
        except:
            retries += 1
            time.sleep(.2)
        else:
            search_succeeded = True
    return search_res_root

@orm.db_session
def fetch_broad_subject_terms():
    """
    Fetches broad subject terms from NLM catalog. Note that only journals
    indexed in MEDLINE have these terms
    """
    BROAD_SUBJECT_TERMS_INDEX_URL = 'https://wwwcf.nlm.nih.gov/serials/journals/index.cfm'
    html = requests.get(BROAD_SUBJECT_TERMS_INDEX_URL, headers=scraper.REQUESTS_AGENT_HEADERS).content.decode(errors='replace')
    soup = BeautifulSoup(html, features='html.parser')
    for a in soup.findAll('a'):
        if a.get('href','').startswith('http://www.ncbi.nlm.nih.gov/nlmcatalog?term='):
            broad_subject_term = BroadSubjectTerm.get(name=a.text)
            if broad_subject_term==None:
                broad_subject_term = BroadSubjectTerm(name=a.text)
                orm.commit()

@orm.db_session
def fetch_journals_info_from_nlmcatalog(broad_subject_term_name='', issn='', verbosity='full'):
    """
    Fetch journal and publisher info for all the journals 
    on nlmcatalog and add them/it to database

    Parameters
    ----------
    broad_subject_term: (str) BroadSubjectTerm names based on NLM Catalog for MEDLINE
    issn: (str)
    verbosity: (str or None) 'full' will print all dois, 'summary' prints the counter every 5 articles, None prints nothing

    Returns
    ---------
    None
    """
    if broad_subject_term_name:
        term = f'{broad_subject_term_name}%5Bst%5D'
    elif issn:
        term = f'"{issn}"%5BISSN%5D'
    else: #> get all
        term = 'currentlyindexed'
    search_res_root = search_nlmcatalog(term=term)
    #> Get the NLM Catalogy IDs
    nlmcatalog_ids = [element.text for element in search_res_root.findall('IdList')[0].getchildren()]
    broad_subject_term = BroadSubjectTerm.get(name=broad_subject_term_name)
    for idx, nlmcatalog_id in enumerate(nlmcatalog_ids):
        if verbosity=='full':
            print(f'{idx+1} of {len(nlmcatalog_ids)}: {nlmcatalog_id}')
        elif verbosity=='summary' and ((idx+1)%5==0):
            print(f'{idx+1} of {len(nlmcatalog_ids)}')
        #> Check if journal already exist and avoid adding it
        #  but add the current subject term to the journal if it's new
        journal = Journal.get(nlmcatalog_id=nlmcatalog_id)
        if journal:
            if broad_subject_term:
                if broad_subject_term not in journal.broad_subject_terms:
                    journal.broad_subject_terms.add(broad_subject_term)
                    orm.commit()
            print('Already exists in db')
            continue
        journal_url = f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nlmcatalog&rettype=xml&id={nlmcatalog_id}'
        fetch_succeeded = False
        retries = 0
        while (retries < 10) and (not fetch_succeeded):
            try:
                journal_res_xml = requests.get(journal_url, headers=scraper.REQUESTS_AGENT_HEADERS).text
                journal_res_root = ET.fromstring(journal_res_xml)
            except:
                time.sleep(.2)
                retries += 1
            else:
                fetch_succeeded = True
        #>> full_name from TitleMain
        if len(journal_res_root.find('NLMCatalogRecord').findall('TitleMain')) > 0:
            full_name = journal_res_root.find('NLMCatalogRecord').find('TitleMain').find('Title').text
            full_name = full_name.rstrip('.') # Remove the trailing "." from the name of some journals
        else:
            if verbosity=='full':
                print(f"No TitleMain")
            continue
        #>> abbr_name from MedlineTA
        if len(journal_res_root.find('NLMCatalogRecord').findall('MedlineTA')) > 0:
            abbr_name = journal_res_root.find('NLMCatalogRecord').find('MedlineTA').text
        else:
            if verbosity=='full':
                print(f"No MedlineTA")
            continue
        #> get ISSNs
        if len(journal_res_root.find('NLMCatalogRecord').findall('ISSN')) > 0:
            issns = [node.text for node in journal_res_root.find('NLMCatalogRecord').findall('ISSN')]
        else:
            if verbosity=='full':
                print(f"No ISSN")
            continue
        #> Get the journal and pmc url (if exists)
        pmc_url = journal_url = ''
        if len(journal_res_root.find('NLMCatalogRecord').findall('ELocationList')) > 0:
            for ELocation in journal_res_root.find('NLMCatalogRecord').find('ELocationList').findall('ELocation'):
                if len(ELocation.findall('ELocationID'))>0:
                    ELocation_url = ELocation.find('ELocationID').text
                    if ELocation_url.startswith('https://www.ncbi.nlm.nih.gov/pmc/journals'):
                        pmc_url = ELocation_url
                    else:
                        journal_url = ELocation_url
        if (pmc_url=='') and (journal_url==''):
            print(f"No pmc/journal url")
            continue
        #> Get the publisher url and domain from journal url
        if journal_url:
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
        else:
            publisher=None
        journal = Journal(
            full_name=full_name, 
            abbr_name=abbr_name, 
            issns=issns,
            nlmcatalog_id=nlmcatalog_id,
            pmc_url=pmc_url,
            publisher=publisher,
            broad_subject_terms=[broad_subject_term])
        #> Save the database
        orm.commit()

@orm.db_session
def resolve_duplicated_journal_abbr_names():
    """
    For the journals fetched from nlmcatalog there are very few journals (with a single abbr_name)
    that have multiple nlmcatalog ids. This function keeps the most recent version (the one with higher id)
    to resolve this issue.

    Returns
    (bool): whether there were any duplicates
    """
    journal_names = pd.Series([j.abbr_name for j in Journal.select()])
    duplicated_journal_names = journal_names[journal_names.duplicated()].values
    if duplicated_journal_names.shape[0] == 0:
        return False
    for duplicated_journal_name in duplicated_journal_names:
        print(duplicated_journal_name)
        journal_versions = Journal.select(abbr_name=duplicated_journal_name).order_by(lambda j: int(j.nlmcatalog_id))
        for obsolete_journal_version in list(journal_versions)[:-1]:
            obsolete_journal_version.delete()
            orm.commit()
    return True

@orm.db_session
def update_supported_publishers():
    """
    Update the supported status of publishers based on current version of scraper
    """
    for publisher_domain in scraper.SUPPORTED_DOMAINS:
        publisher = Publisher.get(domain=publisher_domain)
        publisher.supported=True
    orm.commit()
        

@orm.db_session
def fetch_journal_articles_data(journal_abbr, start_year=0, end_year=None, max_results=0, verbosity='full'):
    """
    Uses PubMed to get the latest articles of a journal based on its name

    Parameters
    ----------
    journal_abbr: (str) journal abbreviation according to NLM catalog
    max_results: (int) number of recent articles to retrieve, 0 will get all the articles
    start_year: (int)
    end_year: (int)
    verbosity: (str or None) 'full' will print all dois, 'summary' prints the counter every 5 articles, None prints nothing

    Returns
    ----------
    articles: (list) a list of entities.Article items
    """
    #> Check if journal/PMC is supported by scraper
    journal = Journal.get(abbr_name=journal_abbr)
    if not journal.publisher.supported:
        print("Journal not supported")
        return []
    #> Search in pubmed
    pubmed = PubMed()
    if not end_year:
        end_year = datetime.date.today().year + 2
    query = f"{journal_abbr}[jour] {start_year}:{end_year}[DP]"
    if not max_results:
        max_results = pubmed.getTotalResultsCount(query)
    entries = list(pubmed.query(query, max_results=max_results))
    articles = []
    counter = 0
    total_count = len(entries)
    for entry in entries:
        # > a quick fix for a bug in pymed (0.8.9), which sometimes returns a multiline list of dois
        # for a entry. And the first one is the real one
        doi = entry.doi.split('\n')[0]
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
        else:
            if verbosity=='full':
                print("Already in database")
        articles.append(article)
        counter+=1
        if verbosity=='full':
            print(f'({counter} of {total_count}): {doi}')
        if (counter%5==0) and (verbosity=='summary'):
            print(counter)

    return articles

def fetch_broad_subject_term_articles_data(broad_subject_term_name, **kwargs):
    """
    A wrapper for fetch_journal_articles_data which gets the data for all the journals
    in a broad subject term.

    Parameters
    ----------
    broad_subject_term_name: (str) NLM catalog broad subject term
    **kwargs will be passed on to fetch_journal_articles_data
    """
    for journal in BroadSubjectTerm.get(name=broad_subject_term_name).journals.order_by(Journal.abbr_name):
        print(journal.abbr_name)
        fetch_journal_articles_data(journal.abbr_name, **kwargs)