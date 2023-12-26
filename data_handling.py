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
from helpers import download_file, pubmed_date_to_datetime

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
            search_res_xml = requests.get(search_url).text
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
    print("Updating supported publishers")
    supported_journals = 0
    for publisher_domain in scraper.SUPPORTED_DOMAINS:
        publisher = Publisher.objects.get(domain=publisher_domain)
        n_journals = len(publisher.journals)
        supported_journals += n_journals
        print(f"{publisher.domain} with {n_journals} journals is supported")
        publisher.supported=True
        publisher.save()
    for publisher in Publisher.objects.filter(supported=True):
        if publisher.domain not in scraper.SUPPORTED_DOMAINS:
            print(publisher.domain, "no longer supported")
            publisher.supported=False
            publisher.save()
    print(f"{supported_journals} of a total number of {Journal.objects.count()} journals in database are supported")

def get_data_pubmed(pmid, verbosity='full', logger=None):
    """
    Get the dates of an article from PubMed
    """
    # note: revised date might not be available or might reflect changes in versions of the article
    # rather than revisions in the review process
    dates = {'Received':None, 'Revised':None, 'Accepted':None, 'Published':None}
    metadata = {}
    url = f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmid}'
    fetch_succeeded = False
    retries = 0
    while (retries < 10) and (not fetch_succeeded):
        try:
            res_xml = requests.get(url).text
            res_root = ET.fromstring(res_xml)
        except:
            time.sleep(.2)
            retries += 1
        else:
            fetch_succeeded = True
    if not fetch_succeeded:
        if verbosity=='full': logger.info("Pubmed fetch failed after 10 retries")
        return dates
    try:
        date_elements = res_root.find('PubmedArticle').find('PubmedData').find('History').findall('PubMedPubDate')
    except AttributeError as e:
        if verbosity=='full': logger.info("No pubmed dates data")
        return dates
    published_date_candidates = {}
    for date_element in date_elements:
        date_type = date_element.get('PubStatus').title()
        if date_type in ['Entrez', 'Pubmed', 'Medline']:
            published_date_candidates[date_type] = pubmed_date_to_datetime(date_element)
        if date_type in dates:
            dates[date_type] = pubmed_date_to_datetime(date_element)
    dates['Published'] = published_date_candidates.get(
        'Entrez', published_date_candidates.get(
            'Pubmed', published_date_candidates.get(
                'Medline', 
                    None)))
    # get metadata
    ## doi    
    for articleid_element in res_root.find('PubmedArticle').find('PubmedData').find('ArticleIdList').findall('ArticleId'):
        if articleid_element.get("IdType")=="doi":
            metadata['doi'] = articleid_element.text
    ## title
    article = res_root.find('PubmedArticle').find('MedlineCitation').find('Article')
    metadata['title'] = article.find('ArticleTitle').text
    ## authors
    metadata['authors'] = []
    for author_element in article.find('AuthorList').findall('Author'):
        author = {}
        author['affiliation'] = []
        for author_element_child in author_element:
            if author_element_child.tag == 'AffiliationInfo':
                author['affiliation'].append(author_element_child.find('Affiliation').text)
            else:
                author[author_element_child.tag.lower()] = author_element_child.text
        author['affiliation'] = '; '.join(author['affiliation'])
        metadata['authors'].append(author)
    return dates, metadata


def fetch_journal_articles_data(journal_abbr, start_year=0, end_year=None, max_results=10000, verbosity='full', logger=None):
    """
    Uses Pubmed/journal website to get the data of latest articles of a journal based on its abbreviated name

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
    if not end_year:
        end_year = datetime.date.today().year + 2
    query = f'"{journal_abbr}"[jour] {start_year}:{end_year}[DP]'
    search_url = f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmax={max_results}&term={query}'
    search_succeeded = False
    retries = 0
    while (retries < 10) and (not search_succeeded):
        try:
            search_res_xml = requests.get(search_url).text
            search_res_root = ET.fromstring(search_res_xml)
        except:
            retries += 1
            time.sleep(.2)
        else:
            search_succeeded = True
    if not search_succeeded:
        if verbosity=='full': logger.info("Pubmed search failed after 10 retries")
        return
    # get journal and publisher
    journal = Journal.objects.get(abbr_name=journal_abbr)
    publisher_Q = Publisher.objects.filter(journals__contains=journal)
    if publisher_Q.count() == 0:
        logger.info("Journal has no publisher")
        return
    else:
        publisher = publisher_Q[0]
    # get data of all pmids
    pmids = [element.text for element in list(search_res_root.find('IdList'))]
    if len(pmids) == 0:
        if verbosity=='full': logger.info(f"No articles found in {start_year}:{end_year}")
        return
    prev_articles = Article.objects.filter(journal=journal)
    prev_pmids = [a.pmid for a in prev_articles]
    prev_dois = [a.doi for a in prev_articles]
    counter = 0
    failed = 0
    total_count = len(pmids)
    any_success = False
    for pmid in pmids:
        article_str = f'[{journal.abbr_name}] ({counter} of {total_count}): {pmid}'
        if pmid in prev_pmids:
            if verbosity=='full': logger.info(f'{article_str} already in db')
            counter+=1
            continue
        start = time.time()
        # first try pubmed, then journal
        where = 'pubmed'
        try:
            dates, metadata = get_data_pubmed(pmid, verbosity=verbosity, logger=logger)
        except AttributeError as e:
            if verbosity=='full': logger.info(f'{article_str} missing pubmed metadata')
            counter+=1
            continue
        # now we have the doi and can skip the article based on doi
        # (as some articles only have doi and no pmid)
        if (metadata['doi'] in prev_dois):
            if verbosity=='full': logger.info(f'{article_str} already in db')
            counter+=1
            # add pmid
            article = Article.objects.filter(doi=metadata['doi'])[0]
            article.pmid = pmid
            article.save()
            continue
        # if pubmed has no dates data, try journal
        if not ((dates['Received'] is not None) & any([v is not None for v in ['Accepted', 'Published']])):
            where = 'journal'
            dates = scraper.get_dates(metadata['doi'], publisher.domain, logger=logger)
        elapsed = time.time() - start
        # if either pubmed or journal has dates data, add the article to db
        if (dates['Received'] is not None) & any([v is not None for v in ['Accepted', 'Published']]):
            article = Article(
                doi=metadata['doi'],
                pmid=pmid,
                title=metadata['title'],
                first_author=f"{metadata['authors'][0].get('lastname','NoLastname')}, {metadata['authors'][0].get('forename', 'NoForeName')}" if len(metadata['authors'])>0 else '',
                last_author=f"{metadata['authors'][-1].get('lastname','NoLastname')}, {metadata['authors'][-1].get('forename', 'NoForeName')}" if len(metadata['authors'])>0 else '',
                first_affiliation=metadata['authors'][0].get('affiliation','NoAffiliation') if len(metadata['authors'])>0 else '',
                last_affiliation=metadata['authors'][-1].get('affiliation','NoAffiliation') if len(metadata['authors'])>0 else '',
                received=dates['Received'],
                accepted=dates['Accepted'],
                published=dates['Published'],
                journal=journal
            )
            article.save()
            any_success = True
            if verbosity=='full': logger.info(f'{article_str} (using {where} in {elapsed:.2f}s)')
        else:
            if verbosity=='full': logger.info(f'{article_str} failed')
            failed += 1
            if (failed >= GIVE_UP_LIMIT) and (not any_success):
                if verbosity=='full': logger.info(f"No success for any of the {GIVE_UP_LIMIT} articles searched")
                journal.update(set__last_failed=True)
                return
        counter+=1
        if (counter%5==0) and (verbosity=='summary'):
            logger.info(counter)
    if any_success:
        journal.last_failed = False
        journal.last_checked = datetime.datetime.now()
        journal.save()
        

def sort_publishers_by_journals_count():
    pipeline = [
        {"$project": {"domain": 1, "url": 1, "supported": 1, "num_journals": {"$size": "$journals"}}},
        {"$sort": {"num_journals": -1}}
    ]
    publishers = Publisher.objects.aggregate(*pipeline)
    return pd.DataFrame(publishers)

# def sort_journals_by_articles_count():
#     return (pd.DataFrame(
#         [[j.abbr_name, len(j.articles)] for j in Journal.objects], 
#         columns=['journal', 'count'])
#         .set_index('journal')['count']
#         .sort_values(ascending=False))

# def get_number_of_journals_w_data():
#     journals_data = Journal.objects.values_list('abbr_name', 'last_failed', 'last_checked')
#     journals_data_df = pd.DataFrame(sorted(journals_data, key=lambda item: (item[2], item[0])))
#     return (journals_data_df[2] != datetime.datetime(2020,1,1)).sum()

# def fetch_journals_list_from_db():
#     journals_list = Journal.objects.values_list('abbr_name')
#     journals_list = sorted(journals_list)
#     with open(JOURNALS_LIST_PATH, 'w') as journals_list_file:
#         journals_list_file.write('\n'.join(journals_list))