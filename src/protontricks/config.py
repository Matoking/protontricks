import configparser
import logging
import os
from pathlib import Path

logger = logging.getLogger("protontricks")


class Config:
    def __init__(self):
        self._parser = configparser.ConfigParser()
        self._path = Path(
            os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
        ) / "protontricks" / "config.ini"

        try:
            content = self._path.read_text(encoding="utf-8")
            self._parser.read_string(content)
        except FileNotFoundError:
            pass

    def get(self, section, option, default=None):
        """
        Get the configuration value in the given section and its field
        """
        self._parser.setdefault(section, {})
        return self._parser[section].get(option, default)

    def set(self, section, option, value):
        """
        Set the configuration value in the given section and its field, and
        save the configuration file
        """
        logger.debug(
            "Setting configuration field [%s][%s] = %s",
            section, option, value
        )
        self._parser.setdefault(section, {})
        self._parser[section][option] = value

        # Ensure parent directories exist
        self._path.parent.mkdir(parents=True, exist_ok=True)

        with self._path.open("wt", encoding="utf-8") as file_:
            self._parser.write(file_)


def get_config():
    """
    Retrieve the Protontricks configuration file
    """
    return Config()
