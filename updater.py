from models import *
import data_handling

import datetime
import gc
import time

import logging

logger = logging.getLogger('main_logger')
logger.setLevel(logging.INFO)
fh = logging.FileHandler('updater.log')
formatter = logging.Formatter("%(asctime)s\t[%(levelname)s]\t%(message)s",
                              "%Y-%m-%d %H:%M:%S")
fh.setFormatter(formatter)
logger.addHandler(fh)


UPDATE_INTERVAL = -1 #days

def update(start_year=2023, end_year=None, domain='all', subject_term=None, skip_last_failed=False):
    """
    A very long function which updates the review speed database until it
    is not needed and then goes into idle mode. This is executed outside
    python by supervisor.

    Parameters
    ----------
    start_year: (int) starting year for pubmed search which is passed on to the scraper
    """
    if not WRITING_ALLOWED:
        logger.info("Writing to db not allowed on this machine")
        return False
    parent_type = 'publisher'
    if domain is None:
        parent_type = 'subject_term'
        if subject_term == 'all':
            parents = BroadSubjectTerm.objects.all()
        else:
            parents = BroadSubjectTerm.objects.filter(name=subject_term)
    elif domain == 'all':
        parents = Publisher.objects.all()
    elif domain == 'supported':
        parents = Publisher.objects.filter(supported=True)
    else:
        parents = Publisher.objects.filter(domain=domain)
    for parent in parents:
        if parent_type == 'publisher':
            parent_name = parent.domain
        else:
            parent_name = parent.name
        logger.info(f'[{parent_name}]')
        #> Get all journals of the publisher
        journals = parent.journals
        for journal in journals:
            logger.info(f'[{journal.abbr_name}]')
            #> Update the journal if it is scrapable (last_failed=False) and its data is > UPDATE_INTERVAL days old
            needs_update = (datetime.datetime.now() - journal.last_checked).days > UPDATE_INTERVAL
            if needs_update:
                if journal.last_failed and skip_last_failed:
                    logger.info(f'[{journal.abbr_name}] failed last time')
                else:
                    data_handling.fetch_journal_articles_data(journal.abbr_name, start_year=start_year, end_year=end_year, logger=logger)
            else:
                logger.info(f'None of {parent_name} journals need update')
                break
            #> Clear the memory and wait 1 sec before going to the next journal
            gc.collect()
            time.sleep(1)

if __name__ == '__main__':
    for subject_term in [
        'Behavioral Sciences', 'Brain', 'Diagnostic Imaging', 
        'Neurology', 'Neurosurgery', 'Psychiatry', 'Psychology',
        'Psychopathology', 'Psychopharmacology', 'Psychophysiology',
        'Radiology', 'Science'
        ]:
        update(start_year=2023, end_year=2023, domain=None, subject_term=subject_term, skip_last_failed=True)