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


UPDATE_INTERVAL = 14 #days

def update(start_year=2020):
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
    #> Get all journals data from the database at once to avoid timeout problems
    journals_data = Journal.objects.values_list('abbr_name', 'last_failed', 'last_checked')
    journals_data = sorted(journals_data, key=lambda item: (item[2], item[0]))
    for journal_data in journals_data:
        abbr_name, last_failed, last_checked = journal_data # which is a tuple
        #> Update the journal if it is scrapable (last_failed=False) and its data is > UPDATE_INTERVAL days old
        needs_update = (datetime.datetime.now() - last_checked).days > UPDATE_INTERVAL
        if needs_update:
            if not last_failed:
                data_handling.fetch_journal_articles_data(abbr_name, start_year=start_year, logger=logger)
            else:
                logger.info(f'[{abbr_name}] scraping failed last time')
        else:
            logger.info(f'No more journals need update')
            break
        #> Clear the memory and wait 1 sec before going to the next journal
        gc.collect()
        time.sleep(1)

if __name__ == '__main__':
    update()