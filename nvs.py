import pandas as pd
from requests_cache import CachedSession
from datetime import timedelta
import logging
_log = logging.getLogger(__name__)
# NVS is updated daily. We cache for a month though bc it is HEAVY
session = CachedSession('nvs_cache', expire_after=timedelta(hours=24 * 30))

def concept_dict_from_collection(collection, collection_type='collection'):
    og1_collection = session.get(f'https://vocab.nerc.ac.uk/{collection_type}/{collection}/current/?_profile=nvs&_mediatype=application/ld+json').json()
    graph = og1_collection['@graph']
    concepts = graph[:-1]
    concepts_dict = {concept['@id']: concept for concept in concepts}
    return concepts_dict

def table_from_collection(collection):
    og1_collection = session.get(f'https://vocab.nerc.ac.uk/collection/{collection}/current/?_profile=nvs&_mediatype=application/ld+json').json()
    graph = og1_collection['@graph']
    concepts = graph[:-1]
    collection = graph[-1]
    concept_dicts = []
    for concept in concepts:
        if type(concept) is not dict:
            _log.debug(f"failed to parse {concept}. skipping")
            continue
        if type(concept['skos:definition']) is dict:
            definition = concept['skos:definition']['@value']
        else:
            definition = concept['skos:definition']
        concept_dict = {'uri': concept['@id'], 'definition': definition}
        if 'skos:prefLabel' in concept.keys():
            concept_dict['cf_standard_name'] = concept['skos:prefLabel']['@value']
        if 'skos:related' in concept.keys():
            related = concept['skos:related']
            if type(related) is not list:
                related = [related]
            for ddict in related:
                if 'P06' in ddict['@id']:
                    concept_dict['units_uri'] = ddict['@id']
        concept_dicts.append(concept_dict)
    df = pd.DataFrame(concept_dicts)
    return df
