# Publisher-specific tests checking if manually extracted dates are
# similar to those scraped automatically
# TODO: Add more instances for each publisher
import main
import datetime


def test_get_dates_springer():
    doi_url = 'https://doi.org/10.1007/s00234-020-02612-8'
    dates = main.get_dates(doi_url)
    assert dates['Received'] == datetime.datetime(2020, 9, 10)
    assert dates['Accepted'] == datetime.datetime(2020, 11, 17)
    assert dates['Published'] == datetime.datetime(2020, 11, 23)

def test_get_dates_karger():
    doi_url = 'https://doi.org/10.1159/000509078'
    dates = main.get_dates(doi_url)
    assert dates['Received'] == datetime.datetime(2020, 5, 21)
    assert dates['Accepted'] == datetime.datetime(2020, 5, 28)
    assert dates['Published'] == datetime.datetime(2020, 7, 30)

def test_get_dates_elsevier():
    doi_url = 'https://doi.org/10.1016/j.clinimag.2020.11.037'
    dates = main.get_dates(doi_url)
    assert dates['Received'] == datetime.datetime(2020, 6, 9)
    assert dates['Accepted'] == datetime.datetime(2020, 11, 10)
    assert dates['Published'] == datetime.datetime(2021, 5, 1)

def test_get_dates_hindawi():
    doi_url = 'https://doi.org/10.1155/2020/5139237'
    dates = main.get_dates(doi_url)
    assert dates['Received'] == datetime.datetime(2020, 7, 7)
    assert dates['Accepted'] == datetime.datetime(2020, 11, 16)
    assert dates['Published'] == datetime.datetime(2020, 11, 27)

def test_get_dates_tandfonline():
    doi_url = 'https://doi.org/10.1080/13803395.2020.1825633'
    dates = main.get_dates(doi_url)
    assert dates['Received'] == datetime.datetime(2020, 1, 12)
    assert dates['Accepted'] == datetime.datetime(2020, 9, 13)
    assert dates['Published'] == datetime.datetime(2020, 10, 6)  

def test_get_dates_scielo():
    doi_url = 'https://doi.org/10.20945/2359-3997000000313'
    dates = main.get_dates(doi_url)
    assert dates['Received'] == datetime.datetime(2020, 2, 6)
    assert dates['Accepted'] == datetime.datetime(2020, 9, 26)

def test_get_dates_viamedica():
    doi_url = 'https://doi.org/10.5603/PJNNS.a2020.0097'
    dates = main.get_dates(doi_url)
    assert dates['Received'] == datetime.datetime(2020, 9, 18)
    assert dates['Accepted'] == datetime.datetime(2020, 12, 2)
    assert dates['Published'] == datetime.datetime(2020, 12, 14)