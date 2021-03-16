from models import *
import data_handling

import datetime
import gc

import logging
logging.basicConfig(filename='updater.log', level=logging.INFO)
logger = logging.getLogger('main_logger')


UPDATE_INTERVAL = 14 #days

def update(start_year=2020):
    if not WRITING_ALLOWED:
        logger.info("Writing to db not allowed on this machine")
        return False
    for broad_subject_term in BroadSubjectTerm.objects.order_by('name'):
        logger.info(broad_subject_term.name)
        journals_count = len(broad_subject_term.journals)
        for idx, journal in enumerate(broad_subject_term.journals):
            logger.info(f'({idx+1} of {journals_count}) {journal.abbr_name}')
            journal_dict = journal.to_mongo().to_dict()
            last_failed = journal_dict.get('last_failed', False)
            needs_update = (datetime.datetime.now() - journal_dict.get('last_checked', datetime.datetime(1900,1,1))).days > UPDATE_INTERVAL
            if needs_update and not last_failed:
                data_handling.fetch_journal_articles_data(journal.abbr_name, start_year=start_year, logger=logger)
                journal.update(set__last_checked=datetime.datetime.now())
            gc.collect()

if __name__ == '__main__':
    update()