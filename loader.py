import configparser
from pathlib import Path
from typing import Dict, Any, Union

class ConfigError(Exception):
    """Custom exception for configuration loading errors."""
    pass

def load_ini_config(config_path: Union[str, Path]) -> Dict[str, Dict[str, Any]]:
    """
    Loads an INI configuration file and returns it as a nested dictionary.

    This function parses a standard .ini file and converts its sections and
    options into a dictionary structure for easy access within the application.
    It automatically attempts to interpret boolean and numeric values.

    Args:
        config_path: The path to the INI configuration file.

    Returns:
        A nested dictionary representing the configuration.
        Example: {'section': {'key': 'value'}}

    Raises:
        ConfigError: If the file is not found or cannot be parsed.
    """
    path = Path(config_path)
    if not path.is_file():
        raise ConfigError(f"Configuration file not found at: {path}")

    config = configparser.ConfigParser()
    try:
        config.read(path)
    except configparser.Error as e:
        raise ConfigError(f"Failed to parse configuration file {path}: {e}") from e

    config_dict = {}
    for section in config.sections():
        config_dict[section] = {}
        for key, value in config.items(section):
            # Attempt to convert types automatically
            if value.lower() in ('true', 'yes', 'on'):
                config_dict[section][key] = True
            elif value.lower() in ('false', 'no', 'off'):
                config_dict[section][key] = False
            else:
                try:
                    # Try converting to int, then float
                    config_dict[section][key] = int(value)
                except ValueError:
                    try:
                        config_dict[section][key] = float(value)
                    except ValueError:
                        config_dict[section][key] = value
                        
    return config_dict
