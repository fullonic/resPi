import json

from scripts.utils import config_from_file

config = config_from_file()
config
config["pump_control_config"]["aqua_volume"] = 20
with open("config.json", "w") as f:
    json.dump(config, f)
