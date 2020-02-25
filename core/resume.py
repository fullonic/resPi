"""Experiment cycle resume generator.

Here we handle the raw information from the whole experiment and generate a resume using
the information of each experiment loop.
"""

import datetime
import os
import shutil
from functools import namedtuple
from pathlib import Path

import statsmodels.api as sm
import pandas as pd

from core.utils import (
    string_to_float,
    delete_excel_files,
    config_from_file,
)

# ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # app root dir
ROOT = Path(__file__).parent.parent  # app root dir
O2Data = namedtuple("O2Data", "min max avg")
R2AB = namedtuple("R2AB", "rsquared a b")
COLS_NAME = [
    "Date &Time [DD-MM-YYYY HH:MM:SS]",
    "Time [sec]",
    "Loop",
    "Phase time [s]",
    "MO2 [mgO2/hr]",
    "slope [mgO2/L/hr]",
    "R^2",
    "max O2 [mgO2/L]",
    "min O2 [mgO2/L]",
    "avg O2 [mgO2/L]",
    "avg temp [°C]",
    "O2 after blank",
]

config = config_from_file()


def temp_mean(series):
    """Get a pandas series and calculate the mean.

    Series row values are float values in string format separated by ",".
    """
    return series.map(string_to_float).mean()


def O2_data(series):
    """O2 calculations."""
    min_ = series.map(string_to_float).min()
    max_ = series.map(string_to_float).max()
    avg_ = series.map(string_to_float).mean()
    return O2Data(min_, max_, avg_)


def trendline_data(df_close, x_column, y_column):
    """Calculate R squared, a and b values."""
    x = df_close[x_column]
    y = df_close[y_column]
    x = sm.add_constant(x.values)
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
        self.dt_col_name = experiment.dt_col_name
        self.df_lists = []
        self.phase_time = (
            f"F{experiment.flush*60}/W{experiment.wait*60}/C{experiment.close*60}"  # noqa
        )

    @property
    def experiment_files(self) -> list:
        """Return the file path of each experiment file.

        List contains: C1, Data file and C2 full path.
        """

        return [f for f in Path(self.experiment.original_file.folder_dst).glob("*.txt")]

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

    def generate_resume(self, control):
        """Create a the daily experiment resume."""
        resume_df = pd.DataFrame(columns=COLS_NAME)
        aqua_volume = config["file_cycle_config"]["aqua_volume"]
        for i, df_close in enumerate(self.experiment.df_loop_generator):
            k = i + 1
            try:
                if str(k) in self.experiment.ignore_loops[self.experiment.original_file.fname]:
                    continue
            except KeyError:
                pass
            O2_col_name = "SDWA0003000061      , CH 1 O2 [mg/L]"
            O2 = O2_data(df_close[O2_col_name])
            r2_a_b = trendline_data(df_close, self.experiment.x, self.experiment.y)
            slope = r2_a_b.b
            O2_HR = slope * aqua_volume

            row = {
                "Date &Time [DD-MM-YYYY HH:MM:SS]": df_close[
                    "Date &Time [DD-MM-YYYY HH:MM:SS]"
                ][0],
                "Time [sec]": len(df_close) + (self.experiment.discard_time * 60),
                "Loop": k,
                "Phase time [s]": self.phase_time,
                "MO2 [mgO2/hr]": O2_HR,
                "slope [mgO2/L/m]": slope,
                "R^2": r2_a_b.rsquared,
                "max O2 [mgO2/L]": O2.max,
                "min O2 [mgO2/L]": O2.min,
                "avg O2 [mgO2/L]": O2.avg,
                "avg temp [°C]": temp_mean(df_close["SDWA0003000061      , CH 1 temp [°C]"]),
                "O2 after blank": O2_HR - control,
            }

            resume_df.loc[k] = row

        self.resume_df = resume_df

    def save(self):
        """Save resume table file to disk."""
        ext = self.experiment.original_file.output
        file_dest = f"{self.experiment.original_file.file_output}.{ext}"
        if ext == "csv":
            self.resume_df.to_csv(file_dest)
        else:
            self.resume_df.to_excel(file_dest, index=False)

    def zip_folder(self):
        """Zip the most recent folder created with excel files."""
        # Full path of the project folder name

        pass
        # TearDown(Path(self.experiment.original_file.file_output).parent).zip_folder()


class ResumeControl(ResumeDataFrame):

    values = []

    def get_bank(self):
        self.generate_resume(0)
        self.save()
        try:
            self.values.append(
                self.resume_df["MO2 [mgO2/hr]"].sum() / len(self.resume_df["MO2 [mgO2/hr]"])
            )
        except ZeroDivisionError:
            print("Control table empty")
            self.values.append(0)

    def calculate_blank(self):
        return (sum(self.values) / len(self.values)) * -1


class TearDown:
    def __init__(self, project_folder):
        self.project_folder = project_folder
        self.graph_preview = Path(ROOT) / "templates/previews"
        self.txt_preview = Path(ROOT) / "static/uploads/preview"

    def organize(self):
        """Zip the most recent folder created with excel files."""
        # Full path of the project folder name
        location = self.project_folder
        graph_folder = Path(location) / "Graphics"
        graph_folder.mkdir()
        data_folder = Path(location) / "Dades"
        data_folder.mkdir()

        for g in Path(location).glob("*.html"):
            shutil.move(str(g), str(graph_folder))

        for d in Path(location).glob("*.xlsx"):
            shutil.move(str(d), str(data_folder))

        # Same as app.config["ZIP_FOLDER"]
        ZIP_FOLDER = os.path.abspath(f"{ROOT}/static/uploads/zip_files")
        # Create the zip file
        zipped = shutil.make_archive(location, "zip", location)
        # Move it to the app zip files folder
        shutil.move(zipped, ZIP_FOLDER)
        # Delete folder data files
        self.delete_project_files()

    def delete_project_files(self):
        """Deletes all residual files from each processing data."""
        # Remove project folder
        shutil.rmtree(self.project_folder)
        # Remove preview global plots and files
        for f in self.txt_preview.glob("*.txt"):
            f.unlink()
        for g in self.graph_preview.glob("*.html"):
            g.unlink()
