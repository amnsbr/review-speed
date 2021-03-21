from models import *
import data_handling

import datetime
import gc
import time

import logging
logging.basicConfig(filename='updater.log', level=logging.INFO)
logger = logging.getLogger('main_logger')


UPDATE_INTERVAL = 14 #days
IDLE_TIME = 24 * 60 * 60 #seconds

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
    for journal in Journal.objects().order_by('last_checked').allow_disk_use(True):
        journal_dict = journal.to_mongo().to_dict()
        last_failed = journal_dict.get('last_failed', False)
        needs_update = (datetime.datetime.now() - journal_dict.get('last_checked', datetime.datetime(1900,1,1))).days > UPDATE_INTERVAL
        if needs_update:
            if not last_failed:
                data_handling.fetch_journal_articles_data(journal.abbr_name, start_year=start_year, logger=logger)
                journal.update(set__last_checked=datetime.datetime.now())
        else:
            #> Since journals are sorted by last_checked, if we reach to a journal
            #  which doesn't need update, the journals after that would also not need
            #  update and the updater should go into the idle mode
            logging.info('Going into idle')
            time.sleep(IDLE_TIME)
            break
        gc.collect()

if __name__ == '__main__':
    update()