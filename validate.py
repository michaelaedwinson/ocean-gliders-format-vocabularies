import yaml
import json
import urllib.request
import logging
_log = logging.getLogger(__name__)

logf = "vocab.log"
logging.basicConfig(
    filename=logf,
    filemode="w",
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

def json_from_uri(uri):
    json_suffix = '?_profile=nvs&_mediatype=application/ld+json'
    json_uri = uri + json_suffix
    with urllib.request.urlopen(json_uri) as url:
        data = json.loads(url.read().decode())
    return data


def validate_sensor(sensor):
    """
    Validate the metadata from a sensor used in the OceanGliders format against the NERC vocab server. Steps:
    1. Check that all mandatory fields are present
    2. Check that sensor_model_vocabulary is a valid URI to the L22 collection
    3. Download the sensor_model_vocabulary record from the NVS and check that all fields match
    4. Check that the NVS L22 item has links to L35 and L05
    5. Make any corrections to the record from recovered NVS entries in L22, L35 and L05
    :param sensor: dictionary of mandatory sensor attributes following OG1
    :return: corrected sensor dict or False if mandatory fields not present or L22 URI not found
    """
    mandatory_keys = {'long_name', 'sensor_maker', 'sensor_maker_vocabulary', 'sensor_model', 'sensor_model_vocabulary', 'sensor_type', 'sensor_type_vocabulary'}
    if set(sensor.keys()) - mandatory_keys:
        _log.error(f"expected keys not found in {sensor}")
        return False
    sensor_model_uri = sensor['sensor_model_vocabulary']
    req = urllib.request.urlopen(sensor_model_uri)
    if req.status != 200:
        _log.error(f"{sensor} URI {sensor_model_uri} not found on NVS. Check URI or log request to add")
        return False
    data = json_from_uri(sensor_model_uri)

    model_name = data['skos:prefLabel']['@value']
    vocab_dict = {'sensor_model_vocabulary': data['@id'],
                  'sensor_model': model_name,
                  'long_name': model_name,}

    broader = data['skos:broader']
    if type(broader) is dict:
        broader = [broader]
    for broader_term in broader:
        if 'L05' in broader_term['@id']:
            l05_uri = broader_term['@id']
            vocab_dict['sensor_type_vocabulary'] = l05_uri
            l05_json = json_from_uri(l05_uri)
            vocab_dict['sensor_type'] = l05_json['skos:prefLabel']['@value']
            if l05_uri in sensor.values():
                break
    related = data['skos:related']
    if type(related) is dict:
        related = [related]
    for related_term in related:
        if 'L35' in related_term['@id']:
            l35_uri = related_term['@id']
            vocab_dict['sensor_maker_vocabulary'] = l35_uri
            l35_json = json_from_uri(l35_uri)
            vocab_dict['sensor_maker'] = l35_json['skos:prefLabel']['@value']
            break
    for key, val in sensor.items():
        if key not in vocab_dict.keys():
            if 'vocabulary' in key:
                _log.warning(f'Missing linkage in BODC. Request link: {vocab_dict['sensor_model']} {vocab_dict['sensor_model_vocabulary']} Related: {sensor[key.replace('_vocabulary', '')]} {val}')
            continue
        if val != vocab_dict[key]:
            _log.info(f'Incorrect yaml entry in {model_name}: {key}: {val} != BODC value: {vocab_dict[key]}. Replacing it')
            sensor[key] = vocab_dict[key]
    return sensor

def validate_sensors_from_yaml():
    with open('yaml/draft_yaml/sensors.yaml') as f:
        draft_sensors = yaml.safe_load(f)
    _log.info(f"START check {len(draft_sensors)} sensors")
    validated_sensors = {}
    for sensor_name, sensor in draft_sensors.items():
        _log.debug(f'Validate {sensor_name}')
        validated = validate_sensor(sensor)
        if validated:
            validated_sensors[sensor_name] = validated
    with open('yaml/validated_yaml/sensors.yaml', 'w') as f:
        yaml.safe_dump(validated_sensors, f)
    _log.info(f"COMPLETE check all sensors. Read {len(draft_sensors)}, wrote {len(validated_sensors)} sensors")


if __name__ == '__main__':
    validate_sensors_from_yaml()