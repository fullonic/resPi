"""File convert utilities."""
import os
import math
import datetime

import chardet
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from scripts.utils import string_to_float, config_from_file, progress_bar

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
    # return [calculate_ox(value) for value in lst_self.time_stamp_code]


class FileFormater:
    """Format a txt file into a excel table."""

    def __init__(self, file_: str):  # noqa
        self.file_ = file_
        self.folder_dst = os.path.dirname(file_)
        self.fname = os.path.basename(file_).split(".")[0]
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

    def information_index(self, df):
        for index, dt in enumerate(df):
            if df.iloc[index][0] == self.dt_col_name:
                return index

    def to_dataframe(self, output="xlsx"):
        df = pd.read_table(self.file_, encoding=self.file_encoding, decimal=",")
        for index, dt in enumerate(df):
            if df.iloc[index][0] == self.dt_col_name:
                break

        col_idx = index
        df = df[col_idx:]
        columns_name = list(df.iloc[0])[:6]
        # Drop all NaN columns
        df = df.dropna(axis=1)
        df = df.iloc[:, 0:6]
        # Set new columns names
        df.columns = columns_name
        df.reset_index(inplace=True, drop=True)
        df.drop(0, 0, inplace=True)  # remove the line were was the columns name

        # Change date time column to a python datetime object
        df[self.dt_col_name] = df[self.dt_col_name].map(convert_datetime)
        self.df = df
        self.output = output
        if self.save_converted:
            self.save(output)

    def save(self, name=None):
        """Export converted DF to a new file."""
        # TODO: Allow user pass a new name for the exported file
        if self.output == "csv":
            self.converted_file = f"{self.file_output}.csv"
            self.df.to_csv(self.converted_file)
        else:
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
        self, flush: int, wait: int, close: int, original_file: str, ignore_loops: list = None
    ):  # noqa
        self.flush = flush
        self.wait = wait
        self.close = close
        self.discard_time = flush + wait  # time-span to discard from each information cycle
        self.loop_time = flush + wait + close

        # LOAD ALL CONFIG FROM FILE
        config = config_from_file()["experiment_file_config"]
        self.dt_col_name = config["DT_COL"]
        self.time_stamp_code = config["TSCODE"]  # Get data column name
        self.O2_COL = config["O2_COL"]  # "SDWA0003000061      , CH 1 O2 [% air saturation]"
        self.x = config["X_COL"]  # column of oxygen evolution self.x
        self.y = config["Y_COL"]
        self.plot_title = config["PLOT_TITLE"]
        self.save_loop_df = config["SAVE_LOOP_DF"]
        self.format_file(original_file)
        self.ignore_loops = ignore_loops or []

    def format_file(self, original_file):
        """For OLSystem output file into a pandas DF."""
        txt_file = FileFormater(original_file)
        txt_file.to_dataframe()
        df = txt_file.df
        for col in df.columns[1:]:
            df[col] = df[col].astype(str)
        self.df = df
        # Solves issues with temperature symbol °C or ?C. Outputs always °C
        columns_name = list(self.df.columns)
        if "SDWA0003000061      , CH 1 temp [?C]" in self.df.columns:
            idx = columns_name.index("SDWA0003000061      , CH 1 temp [?C]")
            columns_name.remove("SDWA0003000061      , CH 1 temp [?C]")
            columns_name.insert(idx, "SDWA0003000061      , CH 1 temp [°C]")

        self.df.columns = columns_name
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
        data = self.df
        start_value = data[self.time_stamp_code].iloc[0]
        data[self.x] = self.df[self.time_stamp_code].apply(calculate_ox, args=(start_value,))
        data[self.y] = data[self.O2_COL].map(string_to_float)
        data.head()
        plot = Plot(
            data,
            self.x,
            self.y,
            "Experiment",
            dst=os.path.dirname(self.original_file.file_output),
        )
        plot.simple_plot(markers)

    @property
    def total_of_loops(self) -> int:
        """Calculate the total amount of time that last the experiment.

        Using the first record and the last one we calculate here the total time.
        Using this total
        (timedelta object) seconds are calculated and divided by the portion of each cycle
        by hour.
        This information is needed in order to calculate the number of cycle of the experiment.
        """
        time_diff = self.df[self.dt_col_name].iloc[-1] - self.df[self.dt_col_name].iloc[0]
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
    def df_close_list(self):  # NOTE:  must pass here list to ignore
        # k = 0
        lst: list = []
        start: int = 0
        end: int = 0
        for k, v in self.loop_data_range.items():  # It will ignore
            # if k in self.ignore_loops:
            #     k += 1
            #     continue
            end += get_loop_seconds(v)
            try:
                df_close = self._close_df(start, end)
            except IndexError:
                break
            start = end + 1
            end += 1
            if self.save_loop_df:
                self.save(df_close, name=str(k))
            lst.append(df_close)
            k += 1
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
        # Create the new column of oxygen evolution
        #  Create a new column for o2 evolution and calculate_ox_evolution
        start_value = df_close[self.time_stamp_code].iloc[0]
        df_close.loc[:, "Temps (min)"] = df_close[self.time_stamp_code].apply(
            calculate_ox, args=(start_value,)
        )
        df_close.loc[:, self.x] = df_close["Temps (min)"].map(lambda x: x / 60)
        df_close.loc[:, self.y] = df_close[self.O2_COL].map(string_to_float)
        return df_close

    @progress_bar
    def create_plot(self, format_="html"):
        """Proxy for Plot object."""
        print("Creating Plots", end="\n")
        step = 100 / len(self.df_close_list)
        for i, df_close in enumerate(self.df_close_list):
            k = i + 1
            Plot(
                df_close,
                self.x,
                self.y,
                self.plot_title,
                dst=os.path.dirname(self.original_file.file_output),
                fname=f"df_plot_{k}",  # TODO: must be user o decides name
            ).create()
            yield round(step * k)

    def save(self, df_loop, name):
        """Save data frame into a excel file."""
        return df_loop.to_excel(f"{self.original_file.folder_dst}/df_loop_{name}.xlsx")


class Plot:
    """Generate all necessary kind of application plots."""

    def __init__(
        self, data, x_axis, y_axis, title, *, dst=None, fname="dataframe", output="html",
    ):  # noqa
        self.data = data
        self.x_axis = x_axis
        self.y_axis = y_axis
        self.title = title
        self.output = output
        self.fname = fname
        self.dst = dst

    def create(self):
        """Create a plot for each close loop data."""
        x = self.data[self.x_axis]
        y = self.data[self.y_axis]
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=x, y=y, name=self.title, line=dict(color="red", width=1), showlegend=True,
            )
        )
        fig1 = px.scatter(self.data, x=x, y=y, trendline="ols")
        trendline = fig1.data[1]
        fig.add_trace(trendline)
        formula, rsqt = trendline.hovertemplate.split("<br>")[1:3]
        title = f"""<b>{self.title}</b><br>{formula}<br>{rsqt}"""
        fig.update_layout(dict(title=title, showlegend=True))

        fig.write_html(f"{self.dst}/{self.fname}.{self.output}")
        return fig1

    def simple_plot(self, markers=[]):
        """Plot all information from document before any kind of data manipulation."""
        from plotly.subplots import make_subplots

        x = self.data[self.x_axis]
        y = self.data[self.y_axis]
        # Create figure with secondary y-axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Scatter(
                x=x, y=y, name=self.title, line=dict(color="blue", width=1), showlegend=True,
            ),
            secondary_y=False,
        )
        temp = [
            string_to_float(t) for t in list(self.data["SDWA0003000061      , CH 1 temp [°C]"])
        ]

        fig.add_trace(
            go.Scatter(
                x=x,
                y=temp,
                name="Temperature",
                line=dict(color="red", width=1),
                showlegend=True,
            ),
            secondary_y=True,
        )
        # # MARKERS
        y = [9.5] * len(markers)
        size = [2] * len(markers)
        loop = [f'<a id="marker_" name="{i + 1}">{i + 1}</a>' for i, _ in enumerate(markers)]

        points = px.scatter(x=markers, y=y, size=size, text=loop)
        fig.add_trace(points.data[0])
        # Set x-axis title
        fig.update_xaxes(title_text="<b>Temps (hr)</b>")
        fig.update_yaxes(title_text="<b>mg O2/l</b>", secondary_y=False)
        fig.update_yaxes(title_text="<b>Temperatura</b>", secondary_y=True)
        template_folder = os.path.join(os.getcwd(), "templates")
        fig.write_html(f"{template_folder}/_preview.html")


ControlFile = ExperimentCycle
