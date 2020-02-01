"""Application utilities.

All the operations here must be independent of the application requests.
"""

import shutil
import os
import time
import json
import subprocess
from datetime import datetime, timedelta

import pandas as pd
import chardet

import plotly.express as px

from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash  # noqa
from flask import session, redirect, url_for

SUPPORTED_FILES = {"txt", "xlsx"}


def _set_time(user_time):
    """Update server time based on user time when started the experiment."""
    update_time = ["sudo", "date", "-s", f"{user_time}"]
    return subprocess.run(update_time)


def string_to_float(n: str) -> float:
    """Convert str item to float."""
    return float(n.replace(",", "."))


def generate_plot(df, plot_name, folder_dst):
    """Create a plot with value from O2 saturation and time stamp code."""
    y, x = df.columns[-2:]
    fig = px.line(df, x=x, y=y, title="O2 Evolution")
    path = os.path.join(folder_dst, plot_name)
    fig.write_html(path)


def file_formatter(file_):
    """Format the original user upload file.

    After uploaded, the file encoding is discovered by using the chardet library.
    Once getting the encode, a data frame is generated only containing the useful information.

    Returns the file path of the cleaned file in format .csv
    """
    # Original file encode
    def get_file_encoding(file_):
        """Get the file path of a file and returns the encoding format."""
        with open(file_, "rb") as f:
            raw = b"".join([f.readline() for _ in range(20)])

        return chardet.detect(raw)["encoding"]

    df_original = pd.read_table(file_, encoding=get_file_encoding(file_))
    df = pd.read_table(file_, encoding=get_file_encoding(file_))

    # Remove top document information
    def get_col_idx(df):
        for index, dt in enumerate(df):
            if df.iloc[index][0] == "Date &Time [DD-MM-YYYY HH:MM:SS]":
                return index

    col_idx = get_col_idx(df)
    df = df_original[col_idx:]

    # NOTE: A flag must be created to check were this line of information real is.
    columns_name = list(df_original.iloc[col_idx])[:6]
    # Drop all NaN columns
    df = df.dropna(axis=1)
    # Set new columns names
    df.columns = columns_name
    df.reset_index(inplace=True, drop=True)
    df.drop(0, 0, inplace=True)  # remove the line were was the columns name

    # Change date time column to a python datetime object
    dt_col_name = "Date &Time [DD-MM-YYYY HH:MM:SS]"
    # if not (dt_col_name in df.columns): TODO: Must create a column name checker
    #     return f"File is missing a column with name {dt_col_name}"
    df[dt_col_name] = df[dt_col_name].map(convert_datetime)
    folder_dst = os.path.dirname(file_)
    fname = os.path.basename(file_).split(".")[0]

    df.to_excel(f"{folder_dst}/{fname}.xlsx")
    return (f"{folder_dst}/{fname}.xlsx", dt_col_name)


def file_reader(ext):
    """File reader function dispatcher based file input extension.

    Using the file extension, here we use return the appropriate pandas method to open that
    specific file type.
    """
    reader = {"xlsx": pd.read_excel, "csv": pd.read_csv, "txt": pd.read_table}
    return reader[ext]


def to_mbyte(size, round_=3):
    """Convert bytes to megabytes."""
    return round(size / 1024 / 1024, round_)


def delete_excel_files(location):
    """Delete all excel files related with the project once they are zipped."""
    shutil.rmtree(location)
    print(f"{location} : Deleted")


def delete_zip_file(location):
    """Remove a zip file with user permission."""
    os.remove(location)
    print(f"{location} : Deleted")


def greeting():
    """Say hey! influenced by the hour of the day."""
    now = datetime.now()
    bona_tarda = datetime(year=now.year, month=now.month, day=now.day, hour=14)
    bon_dia = datetime(year=now.year, month=now.month, day=now.day, hour=6)
    bona_nit = datetime(year=now.year, month=now.month, day=now.day, hour=21)

    if (now < bona_tarda) and (now > bon_dia):
        return "Bon dia"
    elif (now > bona_tarda) and (now < bona_nit):
        return "Bona tarda"
    else:
        return "Bona nit"


def to_js_time(value=None, run_type="auto"):
    """Convert python datetime to javascript datetime.

    Python datetime is converted to milliseconds to meet the same unit than javascript time.
    """
    now = datetime.now()
    # for automatic program
    if run_type == "auto":
        # We are working with seconds
        timer = now + timedelta(seconds=value)
        return int(time.mktime(timer.timetuple()) * 1000)

    # for manual
    return int(time.mktime(now.timetuple()) * 1000)


def convert_datetime(dt: str):
    """Convert a date time str representation to a python datetime object."""
    return datetime.strptime(dt, "%d/%m/%Y %H:%M:%S")


def check_extensions(ext):
    """Check if file extension is allowed."""
    if ext in SUPPORTED_FILES:
        return True
    else:
        return False


def config_from_file(ROOT):
    """Open config file."""
    with open(f"{ROOT}/config.json") as f:
        config = json.load(f)
    return config


def save_config_to_file(new_config, ROOT=None):
    def string_to_int(value):
        """Convert config float type string into float type."""
        try:
            return int(value)
        except ValueError:
            return value.strip()

    config_keys = {
        "pump_control_config": {},
    }
    for k, v in new_config.items():
        config_keys["pump_control_config"].update({k: string_to_int(v)})

    if config_keys["pump_control_config"].setdefault("safe_fish", False):
        config_keys["pump_control_config"]["safe_fish"] = True
    fname = f"{ROOT}/config.json" if ROOT else "config.json"
    with open(fname, "w") as f:
        json.dump(config_keys, f)
    return config_keys


def login_required(fn):
    """Decorate to protected against not authenticated users."""
    # Functions warp
    @wraps(fn)
    def wrap(*args, **kwargs):
        if not session.get("auth", False):
            return redirect(url_for("login"))  # Not authenticated
        return fn(*args, **kwargs)

    return wrap


def check_password(password):
    """Check if password is corrected."""
    # Get hash password from os environment to check if matches NOTE: Must be set on pi env
    hash = os.getenv(
        "hash2",
        "pbkdf2:sha256:150000$pMreM10r$6dc02f2deb0725f1f3c70766f44e2aa45d8614556b48e9165740ac6384b4de79",  # noqa
    )
    check = check_password_hash(hash, password)
    if check:
        session["auth"] = True
        return True
    else:
        session["auth"] = False
        return False
