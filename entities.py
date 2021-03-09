from pony import orm
from datetime import date

db = orm.Database()

class Publisher(db.Entity):
    domain = orm.Required(str)
    url = orm.Required(str)
    supported = orm.Required(bool)
    journals = orm.Set('Journal')

class Journal(db.Entity):
    full_name = orm.Required(str)
    abbr_name = orm.Required(str)
    issn = orm.Required(str)
    nlmcatalog_id = orm.Optional(str)
    pmc_url = orm.Optional(str)
    publisher = orm.Required(Publisher)
    articles = orm.Set('Article')

class Article(db.Entity):
    doi = orm.Required(str)
    title = orm.Optional(str)
    authors = orm.Optional(orm.StrArray)
    journal = orm.Required(Journal)
    received = orm.Optional(date)
    accepted = orm.Optional(date)
    published = orm.Optional(date)



# import dataset
# dataset_db = dataset.connect('sqlite:///review_speed.db')
# sample_article = dataset_db['Articles'].find_one()
# publisher = Publisher(name='Springer', domain='link.springer.com', has_method=True)
# journal = Journal(full_name='Neuroradiology', abbr_name='Neuroradiology', publisher=publisher)
# article = Article(
#             doi_url=sample_article['doi_url'],
#             title='Age at symptom onset influences cortical thinning distribution and survival in amyotrophic lateral sclerosis',
#             authors = [
#                 'Pilar M. Ferraro', 
#                 'Corrado Cabona', 
#                 'Giuseppe Meo', 
#                 'Claudia Rolla-Bigliani', 
#                 'Lucio Castellan', 
#                 'Matteo Pardini', 
#                 'Matilde Inglese', 
#                 'Claudia Caponnetto',
#                 'Luca Roccatagliata'],
#             journal=journal,
#             received=sample_article['Received'],
#             accepted=sample_article['Accepted'],
#             published=sample_article['Published']
#             )

# orm.commit()

# orm.select(a for a in Article if a.journal.abbr_name == 'Neuroradiology')[:]