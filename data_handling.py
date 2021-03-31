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
from models import Publisher, BroadSubjectTerm, Journal, Article
from helpers import download_file

SCIMAGOJR_BASE = 'https://www.scimagojr.com/journalrank.php'
JOURNALS_LIST_PATH = os.path.join('data', 'journals_list.txt')
GIVE_UP_LIMIT = 10

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
            if len(BroadSubjectTerm.objects.filter(name=a.text)) == 0:
                broad_subject_term = BroadSubjectTerm(name=a.text).save()

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
    if broad_subject_term_name:
        broad_subject_term = BroadSubjectTerm.objects.get(name=broad_subject_term_name)
    else:
        broad_subject_term = None
    for idx, nlmcatalog_id in enumerate(nlmcatalog_ids):
        if verbosity=='full':
            print(f'{idx+1} of {len(nlmcatalog_ids)}: {nlmcatalog_id}')
        elif verbosity=='summary' and ((idx+1)%5==0):
            print(f'{idx+1} of {len(nlmcatalog_ids)}')
        #> Check if journal already exist and avoid adding it
        #  but add the current subject term to the journal if it's new
        journal_Q = Journal.objects.allow_disk_use(True).filter(nlmcatalog_id=nlmcatalog_id)
        if journal_Q.count() > 0:
            if broad_subject_term:
                journal = journal_Q[0]
                if broad_subject_term not in journal.broad_subject_terms:
                    broad_subject_term.update(push__journals=journal)
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
        #> Add the journal
        journal = Journal(
            full_name=full_name, 
            abbr_name=abbr_name, 
            issns=issns,
            nlmcatalog_id=nlmcatalog_id,
            pmc_url=pmc_url).save()
        #> Get the publisher url and domain from journal url
        if journal_url:
            journal_url_extract = tldextract.extract(journal_url)
            publisher_url = journal_url_extract.fqdn
            publisher_domain = journal_url_extract.domain
            #> Check if publisher is supported
            publisher_supported = publisher_domain in scraper.SUPPORTED_DOMAINS
            #> Create Publisher (if does not exist) and Journal database instances
            publisher_Q = Publisher.objects.filter(domain=publisher_domain)
            if publisher_Q.count() == 0:
                publisher = Publisher(
                    domain=publisher_domain, 
                    url=publisher_url, 
                    supported=publisher_supported).save()
            else:
                publisher = publisher_Q[0]
            publisher.update(push__journals=journal)

# def resolve_duplicated_journal_abbr_names():
#     """
#     For the journals fetched from nlmcatalog there are very few journals (with a single abbr_name)
#     that have multiple nlmcatalog ids. This function keeps the most recent version (the one with higher id)
#     to resolve this issue.

#     Returns
#     (bool): whether there were any duplicates
#     """
#     journal_names = pd.Series([j.abbr_name for j in Journal.objects])
#     duplicated_journal_names = journal_names[journal_names.duplicated()].values
#     if duplicated_journal_names.shape[0] == 0:
#         return False
#     for duplicated_journal_name in duplicated_journal_names:
#         print(duplicated_journal_name)
#         journal_versions = [(int(j.nlmcatalog_id), j) for Journal.objects.filter(abbr_name=duplicated_journal_name)]
#         journal_versions = sorted(journal_versions, key=lambda item: item[0])
#         for obsolete_journal_version in list(journal_versions)[:-1]:
#             obsolete_journal_version[1].delete()
#     return True

def update_supported_publishers():
    """
    Update the supported status of publishers based on current version of scraper
    """
    for publisher_domain in scraper.SUPPORTED_DOMAINS:
        publisher = Publisher.objects.get(domain=publisher_domain)
        if not publisher.supported:
            print(publisher.domain)
            publisher.supported=True
            publisher.save()
        
def fetch_journal_articles_data(journal_abbr, start_year=0, end_year=None, max_results=10000, verbosity='full', logger=None):
    """
    Uses PubMed to get the latest articles of a journal based on its name

    Parameters
    ----------
    journal_abbr: (str) journal abbreviation according to NLM catalog
    max_results: (int) number of recent articles to retrieve, 0 will get all the articles
    start_year: (int)
    end_year: (int)
    verbosity: (str or None) 'full' will print all dois, 'summary' prints the counter every 5 articles, None prints nothing
    logger: (Logger or None)

    Returns
    ----------
    articles: (list) a list of entities.Article items
    """
    #> Check if journal/PMC is supported by scraper
    journal = Journal.objects.get(abbr_name=journal_abbr)
    publisher_Q = Publisher.objects.filter(journals__contains=journal)
    if publisher_Q.count() == 0:
        logger.info("Journal has no publisher")
        return
    elif not publisher_Q[0].supported:
        logger.info("Journal not supported")
        return
    else:
        publisher = publisher_Q[0]
    #> Search in pubmed
    pubmed = PubMed()
    if not end_year:
        end_year = datetime.date.today().year + 2
    query = f"{journal_abbr}[jour] {start_year}:{end_year}[DP]"
    search_succeeded = False
    retries = 0
    while (retries < 10) and (not search_succeeded):
        try:
            entries = list(pubmed.query(query, max_results=max_results))
        except:
            retries += 1
            time.sleep(.2)
        else:
            search_succeeded = True
    if not search_succeeded:
        if verbosity=='full':
            logger.info("Pubmed search failed after 10 retries")
        return
    articles = []
    counter = 0
    total_count = len(entries)
    any_success = False
    for entry in entries:
        if entry.doi:
            # > a quick fix for a bug in pymed (0.8.9), which sometimes returns a multiline list of dois
            # for a entry. And the first one is the real one
            doi = entry.doi.split('\n')[0]
        else:
            logger.info("No DOI")
            continue
        if Journal.objects.filter(articles__doi=doi).count() == 0: # article does not exist
            dates = scraper.get_dates(doi, publisher.domain, logger=logger)
            if any([v is not None for v in dates.values()]): #> the operation has succeeded
                article = Article(
                    doi=doi,
                    title=entry.title,
                    authors=[f"{a['lastname']} {a['initials']}" for a in entry.authors],
                    received=dates['Received'],
                    accepted=dates['Accepted'],
                    published=dates['Published']
                )
                journal.update(push__articles=article)
                any_success = True
            else:
                if verbosity=='full':
                    logger.info('Scraper failed')
                if (counter+1 > GIVE_UP_LIMIT) and (not any_success):
                    if verbosity=='full':
                        logger.info(f"No success for any of the {GIVE_UP_LIMIT} articles searched")
                    journal.update(set__last_failed=True)
                    return
        else:
            if verbosity=='full':
                logger.info("Already in database")
            any_success = True
        counter+=1
        if verbosity=='full':
            logger.info(f'[{journal.abbr_name}] ({counter} of {total_count}): {doi}')
        if (counter%5==0) and (verbosity=='summary'):
            logger.info(counter)
    journal.update(set__last_failed=False)
    journal.update(set__last_checked=datetime.datetime.now())

def sort_publishers_by_journals_count():
    return (pd.DataFrame(
        [[p.domain, len(p.journals)] for p in Publisher.objects], 
        columns=['publisher', 'count'])
        .set_index('publisher')['count']
        .sort_values(ascending=False))

def sort_journals_by_articles_count():
    return (pd.DataFrame(
        [[j.abbr_name, len(j.articles)] for j in Journal.objects], 
        columns=['journal', 'count'])
        .set_index('journal')['count']
        .sort_values(ascending=False))

def fetch_journals_list_from_db():
    journals_list = Journal.objects.values_list('abbr_name')
    journals_list = sorted(journals_list)
    with open(JOURNALS_LIST_PATH, 'w') as journals_list_file:
        journals_list_file.write('\n'.join(journals_list))