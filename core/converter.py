"""File convert utilities."""
import os
import math
import datetime


import chardet
import pandas as pd


from core.utils import string_to_float, config_from_file, progress_bar
from core.plots import Plot

experiment_file_config = config_from_file()["experiment_file_config"]


def get_loop_seconds(data: dict) -> int:
    """Calculate total loop time in seconds"""
    return (data["end"] - data["start"]).seconds


def convert_datetime(dt: str):
    """Convert a date time str representation to a python datetime object."""
    try:
        return datetime.datetime.strptime(dt, "%d/%m/%Y %H:%M:%S")
    except ValueError:  # only for testing
        try:
            return datetime.datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        except ValueError:  # only for testing
            return datetime.datetime.strptime(dt, "%d/%m/%Y %H:%M")


def calculate_ox(ox_value, start_value):
    """Calculate the evolution of time."""
    return (float(ox_value) - float(start_value)) / 60


class FileFormater:
    """Format a txt file into a excel table."""

    def __init__(self, file_: str):  # noqa
        self.file_ = file_
        self.folder_dst = os.path.dirname(file_)
        self.fname = os.path.basename(file_).split(".")[0]
        if self.fname not in ["C1", "C2"]:
            self.fname = "Experiment"
        self.file_output = f"{self.folder_dst}/{self.fname}"
        config = config_from_file()["experiment_file_config"]
        self.save_converted = config["SAVE_CONVERTED"]
        self.dt_col_name = config["DT_COL"]

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

    def to_dataframe(self, output="xlsx"):
        df = pd.read_table(
            self.file_, encoding=self.file_encoding, decimal=",", low_memory=False
        )
        for col_idx, dt in enumerate(df):
            if df.iloc[col_idx][0] == self.dt_col_name:
                break

        df = df[col_idx:]
        columns_name = list(df.iloc[0])[:6]
        # Drop all NaN columns
        df.dropna(axis=1, inplace=True)
        df = df.iloc[:, 0:6]
        # Set new columns names
        df.columns = columns_name
        df.reset_index(inplace=True, drop=True)
        df.drop(0, 0, inplace=True)  # remove the line were was the columns name

        # Change date time column to a python datetime object
        df.loc[:, self.dt_col_name] = df.loc[:, self.dt_col_name].map(convert_datetime)
        self.output = output
        self.df = df
        if self.save_converted:
            self.save(output)

    def save(self, name=None):
        """Export converted DF to a new file."""
        # TODO: Allow user pass a new name for the exported file
        self.converted_file = f"{self.file_output}.xlsx"
        self.df.to_excel(self.converted_file, index=False)


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
        self,
        flush: int,
        wait: int,
        close: int,
        original_file: str,
        ignore_loops: dict = None,
        file_type: str = None,
    ):  # noqa
        self.flush = flush
        self.wait = wait
        self.close = close
        self.discard_time = (
            flush + wait
        )  # time-span to discard from each information cycle
        self.loop_time = flush + wait + close

        # LOAD ALL CONFIG FROM FILE
        config = config_from_file()["experiment_file_config"]
        self.dt_col_name = config["DT_COL"]
        self.time_stamp_code = config["TSCODE"]  # Get data column name
        self.O2_COL = config[
            "O2_COL"
        ]  # "SDWA0003000061      , CH 1 O2 [% air saturation]"
        self.x = config["X_COL"]  # column of oxygen evolution self.x
        self.y = config["Y_COL"]
        self.plot_title = config["PLOT_TITLE"]
        self.save_loop_df = config["SAVE_LOOP_DF"]
        self.format_file(original_file)
        self.ignore_loops = ignore_loops or {}

        # Console feedback
        if file_type != "test":
            self.file_type = file_type
            print(f"Processament del fitxer <{file_type.title()}>")
            print(
                f"total loops: <{self.total_of_loops}> | completes: <{self.total_loops_completes}>"  # noqa
            )
        else:
            print(f"Comprovació de capçaleres de fitxers ...")

    def format_file(self, original_file):
        """For OLSystem output file into a pandas DF."""
        txt_file = FileFormater(original_file)
        txt_file.to_dataframe()
        df = txt_file.df
        for col in df.columns[1:]:
            df.loc[:, col] = df[col].astype(str)

        # Solves issues with temperature symbol °C or ?C. Outputs always °C
        columns_name = list(df.columns)
        if "SDWA0003000061      , CH 1 temp [?C]" in df.columns:
            idx = columns_name.index("SDWA0003000061      , CH 1 temp [?C]")
            columns_name.remove("SDWA0003000061      , CH 1 temp [?C]")
            columns_name.insert(idx, "SDWA0003000061      , CH 1 temp [°C]")

        df.columns = columns_name
        self.df = df
        self.original_file = txt_file
        self.experiment_plot()

    def experiment_plot(self):
        """Create a global plot of all complete experiment cycle."""
        markers = []
        timer = 0
        for i in range(self.total_of_loops):
            pt = timer + (self.loop_time)
            markers.append(pt)
            timer = pt
        start_value = self.df[self.time_stamp_code].iloc[0]
        self.df[self.x] = self.df[self.time_stamp_code].apply(
            calculate_ox, args=(start_value,)
        )
        self.df[self.y] = self.df[self.O2_COL].map(string_to_float)
        plot = Plot(
            self.df,
            self.x,
            self.y,
            "mg 02/L",
            dst=os.path.dirname(self.original_file.file_output),
        )
        plot.create_global_plot(fname=self.original_file.fname, markers=markers)

    @property
    def total_of_loops(self) -> int:
        """Calculate the total amount of time that last the experiment.
º
        Using the first record and the last one we calculate here the total time.
        Using this total
        (timedelta object) seconds are calculated and divided by the portion of each cycle
        by hour.
        This information is needed in order to calculate the number of cycle of the experiment.
        """
        time_diff = (
            self.df[self.dt_col_name].iloc[-1] - self.df[self.dt_col_name].iloc[0]
        )
        # Put every time value into seconds
        total = (time_diff).seconds / (self.loop_time * 60)
        self.total_loops_completes = int(total)
        # print("total loops", int(total))
        return math.ceil(total)  # rounds up the decimal to number

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
    def df_loop_generator(self):
        """Return a generator with all df loops."""
        start: int = 0
        end: int = 0
        for k, v in self.loop_data_range.items():  # It will ignore
            end += get_loop_seconds(v)
            try:
                df_close = self._close_df(start, end)
            except IndexError:
                break
            start = end + 1
            end += 1
            if self.save_loop_df:
                if self.file_type == "data":
                    self.save(df_close, name=str(k))
                else:
                    self.save(df_close, name=f"control_{str(k)}")

            yield df_close

    def _close_df(self, start: datetime, end: datetime) -> pd.DataFrame:
        """Create a DF with the close information.

        Generate a new df from each individual loop containing only the information from the
        close part of the cycle.
        """
        # Create a new DF with close information
        start = start + (self.discard_time * 60)
        df_close = self.df[start:end].copy()
        df_close.reset_index(inplace=True, drop=True)
        # Create a new column for o2 evolution and calculate_ox_evolution
        start_value = df_close[self.time_stamp_code].iloc[0]
        df_close.loc[:, "Temps (min)"] = df_close[self.time_stamp_code].apply(
            calculate_ox, args=(start_value,)
        )
        # NOTE: Changes if time is minutes (.map(lambda x: x / 60)) or hours
        # df_close.loc[:, self.x] = df_close["Temps (min)"].map(lambda x: x / 60)
        df_close.loc[:, self.x] = df_close["Temps (min)"]
        df_close.loc[:, self.y] = df_close[self.O2_COL].map(string_to_float)
        return df_close

    #@progress_bar
    def create_plot(self, format_="html"):
        """Proxy for Plot object."""
        print("Generació de gràfics", end="\n")
        step = 100 / self.total_of_loops
        for i, df_close in enumerate(self.df_loop_generator):
            k = i + 1
            Plot(
                df_close,
                self.x,
                self.y,
                self.plot_title,
                dst=os.path.dirname(self.original_file.file_output),
                fname=f"{self.original_file.fname}_loop{k}",
            ).create()
            #yield round(step * k)

    def save(self, df_loop, name):
        """Save data frame into a excel file."""
        return df_loop.to_excel(
            f"{self.original_file.folder_dst}/df_loop_{name}.xlsx", index=False
        )


ControlFile = ExperimentCycle
