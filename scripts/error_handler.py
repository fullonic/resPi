"""Confirm that input file have the expected structure."""
import json

from scripts.converter import ExperimentCycle
from scripts.utils import config_from_file

error_template = """Your file value: '{}', is different from the expected value of your
configuration file: '{}'"""

config = config_from_file()["experiment_file_config"]


class HeadersException(Exception):
    """Check that headers are present."""

    def __init__(self, notification):  # noqa
        # super().__init__(col_name, expected_col_name)
        super().__init__(notification)
        # self.col_name = col_name
        # self.expected_col_name = expected_col_name


class WrongDT(HeadersException):
    """Wrong datetime col name."""

    pass


class WrongO2(HeadersException):
    """Wrong O2 col name."""

    pass


class WrongTimeStamp(HeadersException):
    """Wrong Time Stamp Code col name."""

    pass


class HeadersChecker:
    """Check that headers are present."""

    def __init__(self, file_headers):  # noqa
        """All information passed here came directly from the current uploaded file.

        This data will be compared against the expected value from the app configuration file.
        """
        self.file_headers = file_headers
        self.missing = set()

    @property
    def app_config(self):
        """Get configuration from json file.

        Generates a new dictionary using the config values as key values, in order to be able
        to handle missing headers names as missing key values, using KeyError exceptions.
        """
        # Get current configuration from config json file.
        config = config_from_file()["experiment_file_config"]
        # Must have headers
        headers = ["DT_COL", "TSCODE", "O2_COL"]
        _config = {}
        for k, v in config.items():
            if k in headers:
                _config[k] = v
        return _config

    def confirm(self, col_name, expected):
        """Compare headers."""
        error = {"DT_COL": WrongDT, "TSCODE": WrongO2, "O2_COL": WrongTimeStamp}
        try:
            assert expected in self.file_headers  # current uploaded file
        except AssertionError:
            self.missing.add(error_template.format(col_name, expected))
            raise error[col_name](error_template.format(col_name, expected))

    def check(self):
        """Check that current file headers are the same than the ones on configuration file."""
        for col_name in self.app_config:
            self.confirm(col_name, self.app_config[col_name])

        if len(self.missing) == 0:
            self.missing = None


class GUIChecker:
    def __init__(self, file_):
        self.file_ = file_

    def match(self):
        exp = ExperimentCycle(1, 1, 1, self.file_, file_type="test")
        h = HeadersChecker(exp.df.columns)
        try:
            h.check()
            print("")
            return True
        except (WrongDT, WrongO2, WrongTimeStamp):
            return h.missing


checker = GUIChecker
