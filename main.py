from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import datetime
import re
from pymed import PubMed
import pandas as pd
import numpy as np

pubmed = PubMed()

DOI_BASE = 'https://doi.org/'
HEADERS = {"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36"}
EVENTS = ['Received', 'Accepted', 'Published']

#TODO: move these to json files
REGEX_PATTERNS = {
    'scielo':{
        'Received': r'.*Revised:\n\t\t\t\t([a-zA-Z]+) (\d+), (\d+)', # this is an error from publisher, revised is actually received!
        'Accepted': r'.*Accepted:\n\t\t\t\t([a-zA-Z]+) (\d+), (\d+)',
        'Published': None
    },
    'elsevier': {
        'Received': r'.*"Received":"(\d+) ([a-zA-Z]+) (\d+)"',
        'Accepted': r'.*"Accepted":"(\d+) ([a-zA-Z]+) (\d+)"',
        'Published': r'.*"Publication date":"(\d+) ([a-zA-Z]+) (\d+)"'
    },
    'karger': {
        'Received': r'.*Received: ([a-zA-Z]+) (\d+), (\d+)',
        'Accepted': r'.*Accepted: ([a-zA-Z]+) (\d+), (\d+)',
        'Published': r'.*Published online: ([a-zA-Z]+) (\d+), (\d+)',
    },
    'tandfonline': {
        'Received': r'.*Received (\d+) ([a-zA-Z]+) (\d+)',
        'Accepted': r'.*Accepted (\d+) ([a-zA-Z]+) (\d+)',
        'Published': r'.*Published online: (\d+) ([a-zA-Z]+) (\d+)',
    },
    'viamedica': {
        'Received': r'.*Submitted: (\d+)-(\d+)-(\d+)',
        'Accepted': r'.*Accepted: (\d+)-(\d+)-(\d+)',
        'Published': r'.*Published online: (\d+)-(\d+)-(\d+)',
    }
}

DATESTR_PATTERNS = {
    'scielo': 'BdY',
    'elsevier': 'dBY',
    'karger': 'BdY',
    'tandfonline': 'dbY',
    'viamedica': 'Ymd'
}

##########################################################
#################### Helper Functions ####################
##########################################################
def datestr_tuple_to_datetime(datestr_tuple, pattern):
    """
    Converts a tuple of date strings and their pattern to datetime obj
    """
    for datestr_idx in range(3):
        if pattern[datestr_idx] == 'B': # Month name full
            month = datetime.datetime.strptime(datestr_tuple[datestr_idx], '%B').month
        elif pattern[datestr_idx] == 'b': # Month name short
            month = datetime.datetime.strptime(datestr_tuple[datestr_idx], '%b').month
        elif pattern[datestr_idx] == 'm':
            month = int(datestr_tuple[datestr_idx])
        elif pattern[datestr_idx] == 'd':
            day = int(datestr_tuple[datestr_idx])
        elif pattern[datestr_idx] == 'Y':
            year = int(datestr_tuple[datestr_idx])
    return datetime.datetime(year, month, day)

##########################################################
############# Publisher Specific Functions ###############
##########################################################
def springer_get_dates(html):
    soup = BeautifulSoup(html)
    time_elements = soup.findAll('time')
    if len(time_elements) == 4:
        received = datetime.datetime(*map(int, time_elements[1].attrs['datetime'].split('-')))
        accepted = datetime.datetime(*map(int, time_elements[2].attrs['datetime'].split('-')))
        published = datetime.datetime(*map(int, time_elements[3].attrs['datetime'].split('-')))
        return received, accepted, published
    else:
        return None, None, None
    
def hindawi_get_dates(html):
    soup = BeautifulSoup(html)
    if soup.find('span', string='Received'):
        received_str = soup.find('span', string='Received').parent.findAll('span')[-1].text
        received = datestr_tuple_to_datetime(received_str.split(' '), 'dbY')
        accepted_str = soup.find('span', string='Accepted').parent.findAll('span')[-1].text
        accepted = datestr_tuple_to_datetime(accepted_str.split(' '), 'dbY')
        published_str = soup.find('span', string='Published').parent.findAll('span')[-1].text
        published = datestr_tuple_to_datetime(published_str.split(' '), 'dbY')
        return received, accepted, published
    else:
        return None, None, None

SOAP_FUNCITONS = {
    'springer': springer_get_dates,
    'springeropen': springer_get_dates,
    'hindawi': hindawi_get_dates,
}

##########################################################
#################### Main Functions ######################
##########################################################
def get_journal_recent_article_urls(journal_abbr, max_results=50):
    """
    Uses PubMed to get the latest articles of a journal based on its name

    Parameters
    ----------
    journal_abbr: (str) journal abbreviation according to NLM catalog
    max_results: (int) number of recent articles to retrieve

    Returns
    ----------
    urls: (list) a list of doi_urls
    """
    pubmed = PubMed()
    DOI_BASE = 'https://doi.org/'
    urls = []
    entries = pubmed.query(f"{journal_abbr}[jour]", max_results=max_results)
    for entry in entries:
        urls.append(DOI_BASE + entry.doi)
    return urls

def get_article_url_and_publisher(doi_url):
    """
    Converts doi url to article url and returns the domain name as the publisher name
    
    Parameters
    ----------
    doi_url: (str) url of the form https://doi.org/XXXX

    Returns
    ----------
    article_url: (str) url of the page that contains review dates
    publisher: (str) publisher name (e.g. elsevier, tandfonline, etc.)
    """
    #> Get the domain name
    doi_res = requests.get(doi_url, headers=HEADERS)
    domain = urlparse(doi_res.url).netloc
    publisher = domain.split('.')[1]
    #> For some publishers (elsevier) the redirection doesn't work properly, and
    #  we need another publisher-specific way to get to the article_url
    if publisher == 'elsevier':
        sciencedirect_id = doi_res.url.split('/')[-1]
        article_url = 'https://www.sciencedirect.com/science/article/pii/' + sciencedirect_id
    #> But otherwise, return the automatically redirected doi_url as the article_url
    else:
        article_url = doi_res.url
    return article_url, publisher

def get_dates(article_url, publisher):
    """
    Uses Regex or BeautifulSoup to get the datetimes for received, accepted and published
    
    Parameters
    ----------
    article_url: (str) the webpage containing the dates
    publisher: (str) publisher name (e.g. elsevier, tandfonline, etc.)

    Returns
    ----------
    dates: (dict) datetime.datetime objs for three events (Received, Accepted, Published)
    """
    dates = {'Received': None, 'Accepted': None, 'Published': None}
    #> Get the HTML
    try:
        html = requests.get(article_url, headers=headers).content.decode(errors='replace')
    except:
        print("Unable to get article url page")
        return dates
    regex_patterns = REGEX_PATTERNS.get(publisher)
    soap_function = SOAP_FUNCITONS.get(publisher)
    #> For some publishers we can use regex
    if regex_patterns:
        for event, regex in regex_patterns.items():
            try:
                #> Use prespecified regex_patterns to get date tuples, 
                #  e.g.: ('July', '13', '2020'), ('13', '12', '2020'), etc.
                datestr_tuple = re.match(regex, html, flags=re.DOTALL).groups()
            except:
                dates[event] = None
            else:
                #> Convert the tuples to datetime objs based on publisher's datestr pattern,
                #  e.g.: BdY (full month name, day, full year)
                dates[event] = datestr_tuple_to_datetime(datestr_tuple, DATESTR_PATTERNS[publisher])
    #> For others we need specific functions for parsing the HTML
    # TODO: Technically these could also be written as regex patterns
    elif soap_function:
        #> For consistency, the input to all these functions is a html
        #  and the output is a tuple (received, accepted, published)
        parsed_dates = soap_function(html)
        #> Place each datetime in their respective dict cell
        for event_idx in range(3):
            dates[EVENTS[event_idx]] = parsed_dates[event_idx]
    else:
        print(f"{publisher} not supported")
    return dates

def get_review_speed_df(journal_abbr, max_results=50):
    """
    Gets the review speed of recent articles in a journal

    Parameters
    ---------
    journal_abbr: (str) journal abbreviation according to NLM catalog
    max_results: (int) number of recent articles to retrieve


    Returns
    ---------
    review_speed_df: (pd.DataFrame) submission, acceptance and publication date and their respective durations for each article
    """
    #> Initialize the DataFrame (doi_url will be the index)
    review_speed_df = pd.DataFrame(columns=['Submit Date', 'Accept Date', 'Publish Date', 'Submit to Accept', 'Accept to Publish'])
    #> Get doi urls
    doi_urls = get_journal_recent_article_urls(journal_abbr, max_results=max_results)
    print("Fetched Article URLs")
    #> Loop through articles and save their dates
    counter = 0
    for doi_url in doi_urls:
        counter += 1
        article_url, publisher = get_article_url_and_publisher(doi_url)
        review_dates = get_dates(article_url, publisher)
        if (counter % 5 == 0):
            print(counter)
        review_speed_df.loc[doi_url, 'Submit Date'] = review_dates['Received']
        review_speed_df.loc[doi_url, 'Accept Date'] = review_dates['Accepted']
        review_speed_df.loc[doi_url, 'Publish Date'] = review_dates['Published']
    #> Get the differences in the dates of submission, acceptance and publication
    review_speed_df['Submit to Accept'] = (review_speed_df['Accept Date'] - review_speed_df['Submit Date'])
    review_speed_df['Accept to Publish'] = (review_speed_df['Publish Date'] - review_speed_df['Accept Date'])
    review_speed_df['Submit to Publish'] = (review_speed_df['Publish Date'] - review_speed_df['Submit Date'])
    #> Convert doi_url to another column
    review_speed_df.reset_index(drop=False).rename(columns={'index':'url'})
    return review_speed_df