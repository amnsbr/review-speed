"""
Functions for retrieving and storing the data for individual articles
"""
from pymed import PubMed
import sqlite3, dataset
import requests
from bs4 import BeautifulSoup
import tldextract
import xml.etree.ElementTree as ET 
import pandas as pd
import os

import scraper
from entities import orm, db, Publisher, SubjectArea, SubjectCategory, Journal, Article

SCIMAGOJR_BASE = 'https://www.scimagojr.com/journalrank.php'


# Connect to database
DATASET_PATH = 'database.sqlite'
db.bind(provider='sqlite', filename=DATASET_PATH, create_db=True)
db.generate_mapping(create_tables=True)

@orm.db_session
def fetch_scimagojr_areas_categories():
    """
    Fetch the scimagojr subject areas and categories and them to the database
    (Run only once)

    Parameters
    ----------
    None

    Returns
    ---------
    None
    """
    base_html = requests.get(SCIMAGOJR_BASE, headers=scraper.REQUESTS_AGENT_HEADERS).content.decode(errors='replace')
    soup = BeautifulSoup(base_html, features='html.parser')
    areas_ul = soup.find('li', text='All subject areas').parent
    for area_a_element in areas_ul.findAll('a')[1:]:
        subject_area = SubjectArea(
            name=area_a_element.text,
            scimago_code=area_a_element['data-code']
            )
        orm.commit()
    categories_ul = soup.find('li', text=' All subject categories').parent
    for category_a_element in categories_ul.findAll('a')[1:]:
        subject_category_code = category_a_element['data-code']
        subject_area_code = subject_category_code[:2]+'00'
        subject_area = SubjectArea.get(scimago_code=subject_area_code)
        subject_category = SubjectCategory(
            name=category_a_element.text,
            scimago_code=subject_category_code,
            subject_area=subject_area
        )
        orm.commit()

@orm.db_session
def fetch_journal_info_from_nlmcatalog(issn, verbosity='full'):
    """
    Fetch the journal and publisher info based on issn and add them to the database

    Parameters
    ----------
    issn: (str) Journal's ISSN
    verbosity: (str or None) 'full' will print all dois, 'summary' prints the counter every 5 articles, None prints nothing

    Returns
    ---------
    journal: (entities.Journal)
    """
    if Journal.get(issn=issn): #TODO allow multiple issns
        print("Journal already in db")
        return Journal.get(issn=issn)
    #> Search in NLM Catalog using ISSN
    search_url = f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=nlmcatalog&term=%22{issn}%22[ISSN]'
    search_res_xml = requests.get(search_url, headers=scraper.REQUESTS_AGENT_HEADERS).text
    search_res_root = ET.fromstring(search_res_xml)
    #> Check if the search has any results
    if not search_res_root.findall('IdList'):
        if verbosity=='full':
            print("The journal does not exist in NLM catalog")
        return None
    #> Get the NLM Catalogy IDs and fetch its info xml
    #  note: for some ISSNs there are more than one ID, and in most cases one of them is not a journal
    #  and has some field missing (resulting in an error) so it should loop through them and prevent
    #  soap erros by first checking if the element exist and then getting its info
    journal = None # function will return None if all IDs are incomplete
    nlmcatalog_ids = [element.text for element in search_res_root.findall('IdList')[0].getchildren()]
    for nlmcatalog_id in nlmcatalog_ids:
        journal_url = f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nlmcatalog&rettype=xml&id={nlmcatalog_id}'
        journal_res_xml = requests.get(journal_url, headers=scraper.REQUESTS_AGENT_HEADERS).text
        #> Parse the XML and extract fullname and abbr name
        journal_res_root = ET.fromstring(journal_res_xml)
        #>> full_name from TitleMain
        if len(journal_res_root.find('NLMCatalogRecord').findall('TitleMain')) > 0:
            full_name = journal_res_root.find('NLMCatalogRecord').find('TitleMain').find('Title').text
            full_name = full_name.rstrip('.') # Remove the trailing "." from the name of some journals
        else:
            if verbosity=='full':
                print(f"No TitleMain for NLM ID {nlmcatalog_id}")
            continue
        #>> abbr_name from MedlineTA
        if len(journal_res_root.find('NLMCatalogRecord').findall('MedlineTA')) > 0:
            abbr_name = journal_res_root.find('NLMCatalogRecord').find('MedlineTA').text
        else:
            if verbosity=='full':
                print(f"No MedlineTA for NLM ID {nlmcatalog_id}")
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
            print(f"No pmc/journal url for NLM ID {nlmcatalog_id}")
            continue
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
            issn=issn, #TODO: get the other ISSNs as well
            nlmcatalog_id=nlmcatalog_id,
            pmc_url=pmc_url,
            publisher=publisher)
        #> if a nlmcatalog_id has enough data, don't continue the loop to avoid creating multiple
        #  journal instances with the same issn
        break 
    #> Save the database
    orm.commit()
    return journal

@orm.db_session
def fetch_journals_info_from_scimago(subject_area_name, main_subject_category_name=None, verbosity='full'):
    """
    Fetch the journals list based on subject area and category from scimagojr

    Parameters
    ----------
    subject_area_name: (str) scimagojr subject area name
    main_subject_category_name: (str) scimagojr subject category name to search. 
        Note: other overlapping categories may also be added
    verbosity: (str or None) 'full' will print all dois, 'summary' prints the counter every 5 articles, None prints nothing

    Returns
    ---------
    journals: (list) of (entities.Journal)
    """
    #> Generate the url based on area and category
    scimago_url = SCIMAGOJR_BASE
    subject_area_code = SubjectArea.get(name=subject_area_name).scimago_code
    scimago_url += f'?area={subject_area_code}'
    if main_subject_category_name:
        main_subject_category_code = SubjectCategory.get(name=main_subject_category_name).scimago_code
        scimago_url += f'&category={main_subject_category_code}'
    scimago_url += '&out=xls'
    scimago_df = pd.read_csv(scimago_url, sep=";")
    journals = []
    for _, row in scimago_df.iterrows():
        issn_no_dash = row['Issn'].split(',')[0]
        issn = issn_no_dash[:4] + '-' + issn_no_dash[4:]
        if verbosity=='full':
            print(issn)
        journal = fetch_journal_info_from_nlmcatalog(issn)
        if journal: #journal is in nlmcatalogy
            #> Add categories from scimago data
            category_strs = row['Categories'].split(";")
            subject_categories = []
            for category_str in category_strs:
                subject_category_name = category_str[:-5] # removing ' (Q1)'
                subject_categories.append(
                    SubjectCategory.get(name=subject_category_name)
                )
            journal.subject_categories = subject_categories
            #> Add SJR from scimago data
            try:
                journal.sjr = float(row['SJR'].replace(',','.'))
            except:
                journal.sjr = None
            orm.commit()
            journals.append(journal)



@orm.db_session
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