"""Clean excel files and export only useful data.

NOTE:
axis 1 = rows, axis 0 = columns
location: /home/somnium/Desktop/Projects/LAB/data_scraper/LAB.xlsx
"""

import datetime
import os
import math
import shutil

import pandas as pd  # noqa

try:
    import RPi.GPIO as GPIO

    ROOT = os.path.join(os.getcwd(), "resPI")
except RuntimeError:
    GPIO = None  # None means that is not running on raspberry pi
    ROOT = os.getcwd()


from scripts.utils import (
    delete_excel_files,
    file_formatter,
    file_reader,
    calculate_ox,
    generate_plot,
)

ext = None
dt_col_name: str = None  # Name of a column from the original data frame
EXCEL_FILE = None
CYCLE_TIME: datetime = None
LOOPS: int = 0
WAIT_TIME: int = 0
DATA_TIME: int = 0
NEW_COLUMN_NAME: str = ""
PLOT_TITLE: str = ""
CREATE_PLOT: bool = True


def generate_data(flush, wait, close, file_path, new_column_name, plot, plot_title):
    """Get all data from user input form.

    All the process will happen inside raspberry pi
    """
    # Get all data from user
    global dt_col_name, EXCEL_FILE, CYCLE_TIME, LOOPS, WAIT_TIME, DATA_TIME
    global NEW_COLUMN_NAME, PLOT_TITLE, CREATE_PLOT
    WAIT_TIME = flush + wait
    DATA_TIME = close
    CYCLE_TIME = WAIT_TIME + DATA_TIME
    EXCEL_FILE, dt_col_name = file_formatter(file_path)
    fname, ext = os.path.basename(EXCEL_FILE).split(".")
    NEW_COLUMN_NAME = new_column_name
    PLOT_TITLE = plot_title
    CREATE_PLOT = plot
    print(fname, ext)

    # Create the data frame
    df = file_reader(ext)(EXCEL_FILE, index_col=0)
    # TODO: CHECK IF FORMAT AND COLUMNS NAME ARE THE ONES EXCEPTED
    # Create the folder here files will be saved
    basename = os.path.dirname(EXCEL_FILE)
    folder = os.path.join(basename, fname)
    try:
        os.mkdir(folder)
        print(f"New folder created with name {fname}")
    except FileExistsError:
        # NOTE: Must be handle here automatically handled a uui4 string for example
        print("Folder creeation problem.")

    LOOPS = working_time(df)
    ranges = generate_ranges(df)
    # Generate all the operations necessaries to create the file
    generate_files(df, ranges, folder)


def generate_ranges(data):
    """Generate a dictionary of useful working cycle time ranges.

    DATA: pandas data frame column of date and times information

    LOOPS: Number of cycles inside a data frame
    WAIT_TIME: Total wait + flush inserted by user
    DATA_TIME: The of a useful cycle information
    dt_col_name: The name of the column were is the dt information toked from the user input file.
    """
    ranges = {}
    start = data[dt_col_name].iloc[0] + datetime.timedelta(minutes=WAIT_TIME)
    for i in range(LOOPS):
        # Create a dictionary of
        end = start + datetime.timedelta(minutes=DATA_TIME)
        ranges[i] = {"start": start, "end": end}
        start = end + datetime.timedelta(minutes=WAIT_TIME)
    return ranges


def working_time(df):
    """Calculate the total amount of time that last the experiment.

    Using the first record and the last one we calculate here the total time. Using this total
    (timedelta object) seconds are calculated and divided by the portion of each cycle by hour.
    This information is needed in order to calculate the number of cycle of the experiment.
    """
    time_diff = df[dt_col_name].iloc[-1] - df[dt_col_name].iloc[0]
    # Put every time value into seconds
    total = (time_diff).seconds / (CYCLE_TIME * 60)
    # rounds up the decimal number
    return math.ceil(total)


def generate_files(df, ranges, folder):
    """Save each data cycle into it's own file."""
    # Dictionary of ranges to filter the main data frame. kw are used to later save a file.

    count = 1
    for k, mask in ranges.items():
        # Filter by time intervals
        filter_ = (df[dt_col_name] > mask["start"]) & (df[dt_col_name] <= mask["end"])
        # apply the filter to the df and reset indexes
        df_close = df.loc[filter_]
        df_close.reset_index(inplace=True, drop=True)
        time_stamp_code = df_close.columns[1]  # Get data column name
        if len(df_close[time_stamp_code]) == 0:  # avoids save a empty file
            return zip_folder()

        # Create the new column of oxygen evolution
        column_name = NEW_COLUMN_NAME
        #  Create a new column for o2 evolution and calculate_ox_evolution
        start_value = df_close[time_stamp_code].iloc[0]
        df_close[column_name] = df_close[time_stamp_code].apply(
            calculate_ox, args=(start_value,)
        )

        # Generate plot
        if CREATE_PLOT:
            generate_plot(df_close, f"plot_{k+1}.html", folder)
        # Save data frame
        fname = f"dataframe_{k+1}.xlsx"
        df_close.to_excel(os.path.join(folder, fname), index=False)  # will drop indexes
        count += 1
    return zip_folder()


def zip_folder():
    """Zip the most recent folder created with excel files."""
    # Full path of the project folder name
    location = os.path.dirname(os.path.abspath(EXCEL_FILE))
    # Same as app.config["ZIP_FOLDER"]
    ZIP_FOLDER = os.path.abspath(f"{ROOT}/static/uploads/zip_files")
    # Create the zip file
    zipped = shutil.make_archive(location, "zip", location)
    # Move it to the app zip files folder
    shutil.move(zipped, ZIP_FOLDER)
    # Delete folder data files
    delete_excel_files(location)
