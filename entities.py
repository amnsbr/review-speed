from pony import orm
from datetime import date

db = orm.Database()

class Publisher(db.Entity):
    domain = orm.Required(str)
    url = orm.Required(str)
    supported = orm.Required(bool)
    journals = orm.Set('Journal')

class SubjectArea(db.Entity):
    name = orm.Required(str)
    scimago_code = orm.Required(str)
    subject_categories = orm.Set('SubjectCategory')

class SubjectCategory(db.Entity):
    name = orm.Required(str)
    scimago_code = orm.Required(str)
    subject_area = orm.Required(SubjectArea)
    journals = orm.Set('Journal')

class Journal(db.Entity):
    full_name = orm.Required(str)
    abbr_name = orm.Required(str, unique=True)
    issn = orm.Required(str, unique=True)
    nlmcatalog_id = orm.Optional(str)
    pmc_url = orm.Optional(str)
    sjr = orm.Optional(float)
    impact_factor = orm.Optional(float)
    publisher = orm.Required(Publisher)
    subject_categories = orm.Set(SubjectCategory)
    articles = orm.Set('Article')

class Article(db.Entity):
    doi = orm.Required(str)
    title = orm.Optional(str)
    authors = orm.Optional(orm.StrArray)
    journal = orm.Required(Journal)
    received = orm.Optional(date)
    accepted = orm.Optional(date)
    published = orm.Optional(date)