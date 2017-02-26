from pprint import pprint
from operator import itemgetter, attrgetter, methodcaller

import os
import base64
import settings
import logging
import redis

from celery import Celery
from elasticsearch import Elasticsearch
from elasticsearch import TransportError

from github import Github
from langdetect import detect_langs

app = Celery('tasks', broker=os.environ.get('REDIS_URL'))
github = Github(os.environ.get("GITHUB_TOKEN"))
es = Elasticsearch([os.environ.get('ELASTICSEARCH_URL')])
logging.basicConfig(filename='./logs/debug.log',level=logging.INFO)
r = redis.Redis.from_url(os.environ.get('REDIS_URL'))

def lang_dict ( text ):
    """returns a list of languages with probablities
    Args:
        text: Text to analyse
    Returns:
        a structure as follows: langs =[{"en":0.99},{"de":0.1}, {"fr":0.5}]
    """
    try:
        langs = (list(map(lambda langs: dict([str(langs).split(":")]), detect_langs(text)))) if (not text is None) else []
    except:
        logging.info('Could not detect languages.')
        langs =[]
    return langs

def englishness(langs):
    """tries to determine how much english there is in there
    Args:
        text: array of dicts of languages with scores
    Returns:
        return a float that might very well represent something like englishness
        [{"en":0.99}] # 1.0
        [{"en":0.99},{"de":0.01}, {"fr":0.001}] # 0.99
        [{"en":0.99},{"de":0.1}, {"fr":0.5}] # 0.664429530201
        [{"en":0.2},{"de":0.1}, {"fr":0.5}] # 0.285714285714
        [{"en":0.002},{"de":0.1}, {"fr":0.99}] # 0.00201612903226
        [{"de":0.1}, {"fr":0.5}] # 0.0
        [] # None
    """
    english = [d for d in langs if d.get("en") is not None]
    non_english =   [d for d in langs if d.get("en") is None]
    non_english_sorted = sorted(non_english, key=lambda lang: (lang.itervalues().next()), reverse=True) if non_english is not None else None
    if not english and not non_english:
        return None
    if english and not non_english:
        return 1.0
    if not english and non_english:
        return 0.0
    english_score = float(english[0]["en"])
    non_english_top_score = float(non_english_sorted[0].itervalues().next())
    return english_score/(non_english_top_score+english_score)

def main_lang(langs):
    sorted_langs = sorted(langs, key=lambda lang: (lang.itervalues().next()), reverse=True)
    if sorted_langs:
        return sorted_langs[0].popitem()[0]
    else:
        return ""

@app.task
def index_repo(full_name):
    """Indexes entry in Elastic Search
    """
    logging.info("indexing %s", full_name)
    doc = repo_with_human_lang(full_name)
    res = es.index(index="repos", doc_type='repo', id=full_name, body=doc)
    r.set('last_github_repository_id', doc["id"])
    return res

def repo_indexed(doc_id):
    """
    Test, if this task has been run.
    """
    try:
        es.get(index="repos", doc_type='repo', id=doc_id)
        return True
    except TransportError:
        logging.info('Repo document not found.')
    return False

def repo_with_human_lang(full_name):
    """returns some of the properties of the repo and adds lanaguage detetiction elements
    Args:
        repo: Repository to enrich
    Returns:
        a structure with info about the repo as well as the owner
    """
    repo = github.get_repo(full_name)
    r = {}
    readme_base64 = repo.get_readme()
    readme = base64.b64decode(readme_base64.content)
    r["full_name"] = repo.full_name
    readme_human_languages = lang_dict(readme)
    r["readme_human_languages"] = readme_human_languages
    r["readme_englishness"] = englishness(readme_human_languages)
    r["description_human_languages"] = lang_dict(repo.description)
    r["main_lang"] = main_lang(readme_human_languages)
    r["language"] = repo.language
    r["owner"] = repo.owner
    r["stargazers_count"] = repo.stargazers_count
    r["watchers_count"] = repo.watchers_count
    r["forks_count"] = repo.forks_count
    r["created_at"] = repo.created_at
    r["id"] = repo.id
    r["owner"] = {}
    r["owner"]["bio_lang"] = lang_dict(repo.owner.bio)
    r["owner"]["name"] = repo.owner.name
    r["owner"]["company"] = repo.owner.company
    r["owner"]["location"] = repo.owner.location
    r["owner"]["public_repos"] = repo.owner.public_repos
    r["owner"]["contributions"] = repo.owner.contributions
    r["owner"]["followers"] = repo.owner.followers
    r["owner"]["following"] = repo.owner.following
    return r

last_repo = int(r.get('last_github_repository_id'))
count = 0
for repository in github.get_repos(0 if last_repo is None else last_repo):
    count += 1
    try:
        es.indices.create(index='repos')
    except TransportError:
        logging.info('Index Already Created.')
    if not repo_indexed(repository.full_name):
        index_repo.delay(repository.full_name)
   # for the moment we are playing so let's end this after twenty repos.
    if count > 20:
        break