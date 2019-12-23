"""Confirm that input file have the expected structure."""

error_template = """Your file value: '{}', is different from the expected value of your
configuration file: '{}'"""

config = {
    "DT_COL": "Date &Time [DD-MM-YYYY HH:MM:SS]",
    "TSCODE": "Time stamp code",
    "O2_COL": "SDWA0003000061      , CH 1 O2 [mg/L]",
    "X_COL": "x",
    "Y_COL": "y",
}


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

    def __init__(self, dt_col: str, O2_col: str, timestamp_col: str):  # noqa
        """All information passed here came directly from the current uploaded file.

        This data will be compared against the expected value from the app configuration file.
        """
        try:
            self.dt_col = dt_col.strip()
            self.O2_col = O2_col.strip()
            self.timestamp_col = timestamp_col.strip()
        except AttributeError:
            # TODO: Ensure that names are string types, warn user about name convert
            self.dt_col = str(dt_col).strip()
            self.O2_col = str(O2_col).strip()
            self.timestamp_col = str(timestamp_col).strip()
        self.file_headers = {
            "DT_COL": self.dt_col,
            "TSCODE": self.timestamp_col,
            "O2_COL": self.O2_col,
        }
        self.missing = set()

    @property
    def app_config(self):
        """Get configuration from json file.

        Generates a new dictionary using the config values as key values, in order to be able
        to handle missing headers names as missing key values, using KeyError exceptions.
        """
        # Get current configuration from config json file.
        # with open()  # TODO: Create configuration file
        _config = {}
        for k, v in config.items():
            if k in self.file_headers.keys():
                _config[k] = v
        return _config

    def confirm(self, col_name, uploaded, expected):
        """Compare headers."""
        error = {"DT_COL": WrongDT, "TSCODE": WrongO2, "O2_COL": WrongTimeStamp}
        try:
            assert uploaded == expected  # current uploaded file
        except AssertionError:
            self.missing.add(error_template.format(uploaded, expected))
            raise error[col_name](error_template.format(uploaded, expected))

    def check(self):
        """Check that current file headers are the same than the ones on configuration file."""
        for col_name in self.file_headers:
            self.confirm(col_name, self.file_headers[col_name], self.app_config[col_name])

        if len(self.missing) == 0:
            self.missing = None


h = HeadersChecker(
    "Date &Time [DD-MM-YYYY HH:MM:SS]  ",
    "SDWA0003000061      , CH 1 O2 [mg/L]",
    "Timestamp code",
)
try:
    h.check()
except (WrongDT, WrongO2, WrongTimeStamp):
    print(h.missing)
    print("FAILED")
