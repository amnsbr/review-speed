from mongoengine import *
import os

if os.path.exists('mongo_atlas_writing_connection_str'):
    connection_str = open('mongo_atlas_writing_connection_str','r').read()
else:
    connection_str = open('mongo_atlas_reading_connection_str','r').read()
client = connect(host=connection_str)

# from pony import orm
# from datetime import date

# db = orm.Database()

class Article(EmbeddedDocument):
    doi = StringField(required=True)
    title = StringField(required=False)
    authors = ListField(StringField())
    received = DateTimeField(required=False)
    accepted = DateTimeField(required=False)
    published = DateTimeField(required=False)

class Journal(Document):
    full_name = StringField(required=True)
    abbr_name = StringField(required=True)
    issns = ListField(StringField())
    nlmcatalog_id = StringField(required=False)
    pmc_url = StringField(required=False)
    sjr = FloatField(required=False)
    impact_factor = FloatField(required=False)
    articles = ListField(EmbeddedDocumentField(Article))

class BroadSubjectTerm(Document):
    name = StringField(required=True, unique=True)
    journals = ListField(ReferenceField(Journal))

class Publisher(Document):
    domain = StringField(required=True, unique=True)
    url = StringField(required=True, unique=True)
    supported = BooleanField(required=True)
    journals = ListField(ReferenceField(Journal))