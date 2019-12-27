"""File convert utilities."""
import os
import math
import datetime

import chardet
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def get_loop_seconds(data: dict) -> int:
    """Calculate total loop time in seconds"""
    return (data["end"] - data["start"]).seconds


def string_to_float(n: str) -> float:
    """Convert str item to float."""
    return float(n.replace(",", "."))


def convert_datetime(dt: str):
    """Convert a date time str representation to a python datetime object."""
    return datetime.datetime.strptime(dt, "%d/%m/%Y %H:%M:%S")


def calculate_ox(ox_value, start_value):
    """Calculate the evolution of time."""
    return (float(ox_value) - float(start_value)) / 60
    # return [calculate_ox(value) for value in lst_time_stamp_code]


class FileFormater:
    """Format a txt file into a excel table."""

    def __init__(self, file_: str):  # noqa
        self.file_ = file_
        self.folder_dst = os.path.dirname(file_)
        self.fname = os.path.basename(file_).split(".")[0]
        self.file_output = f"{self.folder_dst}/{self.fname}"

    @property
    def file_extension(self):
        """Get file extension."""
        return os.path.basename(self.file_).split(".")[-1]

    @property
    def file_encoding(self):
        """Get encoding from the given text file."""
        with open(self.file_, "rb") as f:
            raw = b"".join([f.readline() for _ in range(20)])

        return chardet.detect(raw)["encoding"]

    def information_index(self, df):
        for index, dt in enumerate(df):
            if df.iloc[index][0] == "Date &Time [DD-MM-YYYY HH:MM:SS]":
                return index

    def to_dataframe(self, output="xlsx"):
        df = pd.read_table(self.file_, encoding=self.file_encoding, decimal=",")
        for index, dt in enumerate(df):
            if df.iloc[index][0] == "Date &Time [DD-MM-YYYY HH:MM:SS]":
                break

        col_idx = index
        df = df[col_idx:]
        columns_name = list(df.iloc[0])[:6]
        # Drop all NaN columns
        df = df.dropna(axis=1)
        # Set new columns names
        df.columns = columns_name
        df.reset_index(inplace=True, drop=True)
        df.drop(0, 0, inplace=True)  # remove the line were was the columns name

        # Change date time column to a python datetime object
        dt_col_name = "Date &Time [DD-MM-YYYY HH:MM:SS]"
        df[dt_col_name] = df[dt_col_name].map(convert_datetime)
        self.df = df
        self.output = output

    def save(self, name=None):
        """Export converted DF to a new file."""
        # TODO: Allow user pass a new name for the exported file
        if self.output == "csv":
            self.converted_file = f"{self.file_output}.csv"
            self.df.to_csv(self.converted_file)
        else:
            self.converted_file = f"{self.file_output}.xlsx"
            self.df.to_excel(self.converted_file)


class ExperimentCycle:
    """Convert a txt file data frame into excel table.

    Accepts a .txt file from respiratory system and converts in chucks of data cycle.

    flush: time that pump will be working
    wait: how long will take from when pump stops and close time
    close: period of interests in data record.
    discard_time: total of time that will be discard per cycle on data frame creation.
        cycle = flush + wait + close
    dt_col_name: Name of that contains the experiment time spans
    """

    def __init__(
        self, flush: int, wait: int, close: int, original_file: str, dt_col_name: str
    ):  # noqa
        self.flush = flush
        self.wait = wait
        self.close = close
        self.discard_time = (
            flush + wait
        )  # time-span to discard from each information cycle
        self.loop_time = flush + wait + close
        self.dt_col_name = dt_col_name
        self.format_file(original_file)

    def format_file(self, original_file):
        txt_file = FileFormater(original_file)
        txt_file.to_dataframe()
        self.df = txt_file.df
        self.original_file = txt_file

    @property
    def total_of_loops(self) -> int:
        """Calculate the total amount of time that last the experiment.

        Using the first record and the last one we calculate here the total time. Using this total
        (timedelta object) seconds are calculated and divided by the portion of each cycle by hour.
        This information is needed in order to calculate the number of cycle of the experiment.
        """
        dt_col_name = "Date &Time [DD-MM-YYYY HH:MM:SS]"
        time_diff = self.df[dt_col_name].iloc[-1] - self.df[dt_col_name].iloc[0]
        time_diff.seconds
        # Put every time value into seconds
        total = (time_diff).seconds / (self.loop_time * 60)
        # rounds up the decimal number
        return math.ceil(total)

    @property
    def loop_data_range(self) -> dict:
        """Create a time ranges of each complete loop of the experiment."""
        loop_range = {}
        start = self.df[self.dt_col_name].iloc[0]
        for i in range(self.total_of_loops):
            end = start + datetime.timedelta(minutes=self.loop_time)
            loop_range[i + 1] = {"start": start, "end": end}
            start = end + datetime.timedelta(minutes=self.loop_time)
        return loop_range

    @property
    def loop_close_range(self) -> dict:
        """Create a time ranges of each close part of the experiment."""
        close_range = {}
        start = self.df[self.dt_col_name].iloc[0] + datetime.timedelta(
            minutes=self.discard_time
        )
        for i in range(self.total_of_loops):
            end = start + datetime.timedelta(minutes=self.close)
            close_range[i + 1] = {"start": start, "end": end}
            start = end + datetime.timedelta(minutes=self.discard_time)
        return close_range

    @property
    def df_close_list(self):
        lst = []
        start = 0
        end = 0
        for k, v in self.loop_data_range.items():
            end += get_loop_seconds(v)
            df_close = self._close_df(start, end)
            start = end + 1
            end += 1
            lst.append(df_close)
        return lst

    def _close_df(self, start: datetime, end: datetime) -> pd.DataFrame:
        """Create a DF with the close information.

        Generate a new df from each individual loop containing only the information from the
        close part of the cycle.
        """
        # Create a new DF with close information
        start = start + (self.discard_time * 60)
        df_close = self.df[start:end]
        df_close.reset_index(inplace=True, drop=True)
        time_stamp_code = "Time stamp code"  # Get data column name
        # Create the new column of oxygen evolution
        column_name = "x"
        #  Create a new column for o2 evolution and calculate_ox_evolution
        start_value = df_close[time_stamp_code].iloc[0]
        df_close[column_name] = df_close[time_stamp_code].apply(
            calculate_ox, args=(start_value,)
        )
        O2_col_name = "SDWA0003000061      , CH 1 O2 [mg/L]"
        # O2_col_name = "SDWA0003000061      , CH 1 O2 [% air saturation]"
        df_close["y"] = df_close[O2_col_name].map(string_to_float)
        return df_close

    def create_plot(self):
        for i, df_close in enumerate(self.df_close_list):
            x = df_close["x"]
            y = df_close["y"]
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    name="O2",
                    line=dict(color="red", width=1),
                    showlegend=True,
                )
            )
            fig1 = px.scatter(df_close, x="x", y="y", trendline="ols")
            trendline = fig1.data[1]
            fig.add_trace(trendline)
            fig.update_layout(dict(title="O2"))

            fig.write_html(f"{self.original_file.file_output}_plot_{i + 1}.html")

    def save(self):
        pass


class Plot:
    pass
