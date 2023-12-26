from mongoengine import *
import os

if os.path.exists('mongo_atlas_writing_connection_str'):
    connection_str = open('mongo_atlas_writing_connection_str','r').read().rstrip('\n')
    WRITING_ALLOWED = True
else:
    connection_str = open('mongo_atlas_reading_connection_str','r').read().rstrip('\n')
    WRITING_ALLOWED = False
client = connect(host=connection_str)

class Article(Document):
    doi = StringField(required=False)
    pmid = StringField(required=False)
    title = StringField(required=False)
    first_author = StringField(required=False)
    last_author = StringField(required=False)
    first_affiliation = StringField(required=False)
    last_affiliation = StringField(required=False)
    received = DateTimeField(required=False)
    revised = DateTimeField(required=False)
    accepted = DateTimeField(required=False)
    published = DateTimeField(required=False)
    journal = ReferenceField('Journal')

class Journal(Document):
    full_name = StringField(required=True)
    abbr_name = StringField(required=True)
    issns = ListField(StringField())
    nlmcatalog_id = StringField(required=False)
    pmc_url = StringField(required=False)
    sjr = FloatField(required=False)
    impact_factor = FloatField(required=False)
    last_failed = BooleanField(required=False) 
    last_checked = DateTimeField(required=False)

class BroadSubjectTerm(Document):
    name = StringField(required=True, unique=True)
    journals = ListField(ReferenceField(Journal))

class Publisher(Document):
    domain = StringField(required=True, unique=True)
    url = StringField(required=True, unique=True)
    supported = BooleanField(required=True)
    journals = ListField(ReferenceField(Journal))