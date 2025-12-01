import datetime
import yaml
import logging
import nvs
_log = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("vocab.log", 'w'),
        logging.StreamHandler()
    ]
)

og1 = nvs.concept_dict_from_collection('OG1')
l22 = nvs.concept_dict_from_collection('L22')
p02 = nvs.concept_dict_from_collection('P02')
p01 = nvs.concept_dict_from_collection('P01')
p06 = nvs.concept_dict_from_collection('P06')
l05 = nvs.concept_dict_from_collection('L05')
l35 = nvs.concept_dict_from_collection('L35')

og1_p01_p02 = p01 | p02 | og1
df_p07 = nvs.table_from_collection('P07')

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
    if sensor_model_uri not in l22.keys():
        _log.error(f"URI {sensor_model_uri} not found on NVS. Check URI or log request to add")
        return False
    data = l22[sensor_model_uri]

    model_name = data['skos:prefLabel']['@value']
    vocab_dict = {'sensor_model_vocabulary': data['@id'],
                  'sensor_model': model_name,
                  'long_name': model_name,}

    broader = data['skos:broader']
    in_og_scheme = False
    if 'skos:inScheme' in data.keys():
        in_scheme = data['skos:inScheme']
        if type(in_scheme) is dict:
            in_scheme = [in_scheme]
        for scheme_dict in in_scheme:
            if 'OG_SENSORS' in scheme_dict['@id']:
                in_og_scheme = True
    if not in_og_scheme:
        _log.warning(f'{model_name} {sensor_model_uri} not in http://vocab.nerc.ac.uk/scheme/OG_SENSORS/current/')
    if type(broader) is dict:
        broader = [broader]
    for broader_term in broader:
        if 'L05' in broader_term['@id']:
            l05_uri = broader_term['@id']
            vocab_dict['sensor_type_vocabulary'] = l05_uri
            l05_json = l05[l05_uri]
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
            l35_json = l35[l35_uri]
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
    with open('yaml/draft_yaml/voto_sensors.yaml') as f:
        draft_sensors = yaml.safe_load(f)
    _log.info(f"START check {len(draft_sensors)} sensors")
    validated_sensors = {}
    for sensor_name, sensor in draft_sensors.items():
        _log.debug(f'Validate {sensor_name}')
        validated = validate_sensor(sensor)
        if validated:
            validated_sensors[validated['sensor_model']] = validated
    with open('yaml/validated_yaml/og1_sensors.yaml', 'w') as f:
        yaml.safe_dump(validated_sensors, f)
    _log.info(f"COMPLETE check all sensors. Read {len(draft_sensors)}, wrote {len(validated_sensors)} sensors")


def validate_variable(var_name, variable):
    """
    Validate the metadata from a variables used in the OceanGliders format against the NERC vocab server. Steps:
    1. Assign mandatory coordinates "TIME, LONGITUDE, LATITUDE, DEPTH"
    2. If _FillValue is not present, assign in the value NaNf
    3. Check that all mandatory attributes are present
    4. Check that the vocabulary URI is present in the OG1, P02 or P02 collections
    5. Check that the standard_name is present in the P07 CF standard names vocab
    6. If long_name is missing, assign the value from P07 description with spaces replacing underscores
    7. Check units of the standard_name against the linked P06 entry CHECK CURRENTLY BYPASSED
    :param var_name: dictionary of variable attributes for OG1
    :param variable: name of variable (used for log messages)
    :return: dict of corrected variable attricubutes or False if a check fails
    """
    if var_name not in ["TIME", "LONGITUDE", "LATITUDE", "DEPTH"]:
        variable['coordinates'] =  "TIME, LONGITUDE, LATITUDE, DEPTH"
    if not '_FillValue' in variable.keys():
        variable['_FillValue'] = 'NaNf'
    mandatory_keys = {'standard_name', 'vocabulary', 'units'}
    missing_keys =  mandatory_keys - set(variable.keys())
    if missing_keys:
        _log.error(f"expected keys {missing_keys} not found in {var_name}")
        return False

    variable_uri = variable['vocabulary']
    if variable_uri not in og1_p01_p02.keys():
        _log.error(f"{var_name} URI {variable_uri} not found on NVS. Check URI or log request to add")
        return False
    standard_name =  variable['standard_name']
    if standard_name not in df_p07['cf_standard_name'].values:
        _log.error(f'{var_name} standard name {standard_name} not found in P07')
        return False
    if not 'long_name' in variable.keys():
        variable['long_name'] = variable['standard_name'].replace('_', ' ')

    concept = og1_p01_p02[variable_uri]
    units_uri = df_p07.loc[df_p07['cf_standard_name']==standard_name, 'units_uri'].values[0]
    # Get units directly from the concept if they are linked
    if  'skos:related' in concept.keys():
        related = concept['skos:related']
        if type(related) is dict:
            related = [related]
        for related_term in related:
            if 'P06' in related_term['@id']:
                units_uri = related_term['@id']
                break
    unit_dict = p06[units_uri]

    accepted_units = [unit_dict['skos:prefLabel']['@value'], unit_dict['skos:altLabel']]
    if variable['units'] not in accepted_units:
        _log.error(f'{var_name} unit {variable["units"]} not in expected units {accepted_units} from {units_uri}')
    return variable


def validate_variables_from_yaml():
    validated_variables = {}
    input_variables = {}
    for input_file in ['yaml/draft_yaml/voto_variables.yaml', 'yaml/draft_yaml/og1_coordinates.yaml']:
        with open(input_file) as f:
            draft_variables = yaml.safe_load(f)
        input_variables = input_variables | draft_variables
        _log.info(f"START check {len(draft_variables)} variables")
        for var_name, variables in draft_variables.items():
            _log.debug(f'Validate {var_name}')
            validated = validate_variable(var_name, variables)
            if validated:
                validated_variables[var_name] = validated
    with open('yaml/validated_yaml/og1_variables.yaml', 'w') as f:
        yaml.safe_dump(validated_variables, f)
    _log.info(f"COMPLETE check all variables, read {len(input_variables)} unique variables, wrote {len(validated_variables)} variables")

if __name__ == '__main__':
    start = datetime.datetime.now()
    validate_sensors_from_yaml()
    validate_variables_from_yaml()
    _log.info(f"COMPLETE in {datetime.datetime.now() - start}")