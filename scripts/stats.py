"""Experiment cycle resume generator.

Here we handle and the raw information from the whole experiment and generate a resume using
the information of each experiment loop.
"""

import datetime
import os
import shutil
from functools import namedtuple

import statsmodels.api as sm
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from scripts.utils import (
    delete_excel_files)

O2Data = namedtuple("O2Data", "min max avg")
R2AB = namedtuple("R2AB", "rsquared a b")
COLS_NAME = [
    "Date &Time [DD-MM-YYYY HH:MM:SS]",
    "Time [sec]",
    "Loop",
    "Phase time [s]",
    "CH 1 MO2 [mgO2/hr]",
    "CH 1 slope [mgO2/L/hr]",
    "CH 1 R^2",
    "CH 1 max O2 [mgO2/L]",
    "CH 1 min O2 [mgO2/L]",
    "CH 1 avg O2 [mgO2/L]",
    "CH 1 avg temp [°C]",
    "CH 1 avg Uspeed [cm/s]",
    "CH 1 avg Uswim [BL/s]",
]

def string_to_float(n: str) -> float:
    """Convert str item to float."""
    return float(n.replace(",", "."))


def temp_mean(series):
    """Get a pandas series and calculate the mean.

    Series row values are float values in string format separated by ",".
    """
    return series.map(string_to_float).mean()


def calculate_ox(ox_value, start_value):
    """Calculate the evolution of time."""
    return (ox_value - start_value) / 60


def O2_data(series):
    """O2 calculations."""
    min_ = series.map(string_to_float).min()
    max_ = series.map(string_to_float).max()
    avg_ = series.map(string_to_float).mean()
    return O2Data(min_, max_, avg_)


def trendline_data(df_close):
    """Calculate R squared, a and b values."""
    x = df_close["x"]
    y = df_close["y"]
    x = sm.add_constant(x)
    model = sm.OLS(y, x)
    results = model.fit()
    # Values
    rsquared = results.rsquared
    a = results.params[0]
    b = results.params[1]
    return R2AB(rsquared, a, b)


class ResumeDataFrame:
    """Generate the resume of a complete experiment cycle divided by loops."""

    def __init__(self, experiment):
        """Complete experiment data frame."""
        self.original_df = experiment.df
        self.experiment = experiment
        self.dt_col_name = "Date &Time [DD-MM-YYYY HH:MM:SS]"
        self.df_lists = []
        self.phase_time = (
            f"F{experiment.flush*60}/W{experiment.wait*60}/C{experiment.close*60}"
        )  # noqa

    @property
    def loop_data_range(self) -> dict:
        """Create a time ranges of each complete loop of the experiment."""
        loop_range = {}
        start = self.original_df[self.dt_col_name].iloc[0]
        for i in range(self.experiment.total_of_loops):
            end = start + datetime.timedelta(minutes=self.experiment.loop_time)
            loop_range[i + 1] = {"start": start, "end": end}
            start = end + datetime.timedelta(minutes=self.experiment.loop_time)
        return loop_range

    def generate_resume(self):
        """Create a the daily experiment resume."""
        resume_df = pd.DataFrame(columns=COLS_NAME)

        # start = 0
        # end = 0
        for i, df_close in enumerate(self.experiment.df_close_list):
            # for k, v in self.loop_data_range.items():
            k = i + 1
            O2_col_name = "SDWA0003000061      , CH 1 O2 [mg/L]"
            # O2_col_name = "SDWA0003000061      , CH 1 O2 [% air saturation]"

            O2 = O2_data(df_close[O2_col_name])
            r2_a_b = trendline_data(df_close)

            row = {
                "Date &Time [DD-MM-YYYY HH:MM:SS]": df_close[
                    "Date &Time [DD-MM-YYYY HH:MM:SS]"
                ][0],
                "Time [sec]": len(df_close) + (self.experiment.discard_time * 60),
                "Loop": k,
                "Phase time [s]": self.phase_time,
                "CH 1 MO2 [mgO2/hr]": "",
                "CH 1 slope [mgO2/L/hr]": r2_a_b.b * 60,
                "CH 1 R^2": r2_a_b.rsquared,
                "CH 1 max O2 [mgO2/L]": O2.max,
                "CH 1 min O2 [mgO2/L]": O2.min,
                "CH 1 avg O2 [mgO2/L]": O2.avg,
                "CH 1 avg temp [°C]": temp_mean(
                    df_close["SDWA0003000061      , CH 1 temp [°C]"]
                ),
                "CH 1 avg Uspeed [cm/s]": "",
                "CH 1 avg Uswim [BL/s]": "",
            }

            resume_df.loc[k] = row

        self.resume_df = resume_df

    def save(self):
        ext = self.experiment.original_file.output
        fname = f"{self.experiment.original_file.file_output}.{ext}"
        if ext == "csv":
            self.resume_df.to_csv(fname)
        else:
            self.resume_df.to_excel(fname)

        self.zip_folder()

    def zip_folder(self):
        """Zip the most recent folder created with excel files."""
        # Full path of the project folder name
        location = os.path.dirname(os.path.abspath(self.experiment.original_file.file_output))
        # print(os.path.abspath(__file__))
        print(os.path.dirname(os.path.abspath(self.experiment.original_file.file_output)))
        print(f"{location=}")
        # Same as app.config["ZIP_FOLDER"]
        ZIP_FOLDER = os.path.abspath(f"static/uploads/zip_files")
        print(f"{ZIP_FOLDER=}")
        # Create the zip file
        zipped = shutil.make_archive(location, "zip", location)
        print(f"{zipped=}")
        # Move it to the app zip files folder
        shutil.move(zipped, ZIP_FOLDER)
        # Delete folder data files
        # delete_excel_files(location)
