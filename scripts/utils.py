"""Application utilities.

All the operations here must be independent of the application requests.
"""

import shutil
import os
import time
import json
import subprocess
from datetime import datetime, timedelta
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
