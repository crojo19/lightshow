import os
import json

# Global
DEBUG = False
CONFIG_FILE = "config.json"


# Checks if config file exists
def config_file_exists():
    try:
        if DEBUG: print("Verifying if configuration file exists")
        open(CONFIG_FILE, 'r')
        if DEBUG: print("Configuration file found")
        return True
    except:
        if DEBUG: print("Configuration file doesn't exist creating")
        f = open(CONFIG_FILE, 'w')
        f.close()
        return True


# read config file and return requested item
# if nothing is passed, return entire config file
def read_config_file(config_item=None):
    try:
        if DEBUG: print("Reading Configuration File")
        config_file = open(CONFIG_FILE, 'r')
        config = json.loads(config_file.read())
        config_file.close()
        if DEBUG: print(config)
        if config_item is None:
            return config
        else:
            return config[config_item]
    except:
        return print("404 Not Found")


# validate config file
# Validation_items list of items to confirm exist []
def validate_config_file(validation_items):
    try:
        if DEBUG: print("Reading Configuration File")
        config_file = open(CONFIG_FILE, 'r')
        config = json.loads(config_file.read())
        config_file.close()
        for item in validation_items:
            if config[item] is None: return False
        if DEBUG: print("config file valid")
        return True
    except:
        if DEBUG: print("error while validating config file")
        return False


# write data to config file dict[tag]
def put_config_items(config_dict):
    config = {}
    if config_file_exists():
        if DEBUG: print("Read Data from config file")
        config_file = open(CONFIG_FILE, 'r')
        config = json.loads(config_file.read())
        config_file.close()
    if DEBUG: print("Write Data to config file")
    for item in config_dict.keys():
        config[item] = config_dict[item]
    f = open(CONFIG_FILE, 'w')
    f.write(json.dumps(config))
    f.close()
    return json.dumps(config)


# config_items = [tag, tag, tag]
def get_config_items(self, config_items=None):
    config_dict = {}
    if config_items is None:
        config_dict = self.read_config_file()
    elif isinstance(config_items, list):
        for item in config_items:
            config_dict[item] = self.read_config_file(config_item=item)
    elif isinstance(config_items, str):
        config_dict[item] = self.read_config_file(config_item=config_items)
    return json.dumps(config_dict)
