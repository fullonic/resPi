"""Application utilities.

All the operations here must be independent of the application requests.
"""

import shutil
import sys
import os
import json
from datetime import datetime
from pathlib import Path

SUPPORTED_FILES = ["txt", "xlsx"]


def global_plots(
    flush: int,
    wait: int,
    close: int,
    files: list,
    preview_folder,
    keep=False,
    folder_dst=None,
):
    """Proxy function to deal with global graphs."""
    from core.converter import ExperimentCycle

    if not keep:
        for f in files:
            file_path = str(Path(preview_folder) / f.filename)
            f.save(file_path)

            experiment = ExperimentCycle(
                flush, wait, close, file_path, file_type=f"{f.name}_Vista Preview"
            )
            experiment.experiment_plot()
    else:
        for f in files:
            experiment = ExperimentCycle(
                flush, wait, close, f, file_type=f"{f.name}"
            )
            experiment.experiment_plot()


def string_to_float(n: str) -> float:
    """Convert str item to float."""
    try:
        return float(n.replace(",", "."))
    except AttributeError:
        return n


def to_mbyte(size, round_=3):
    """Convert bytes to megabytes."""
    return round(size / 1024 / 1024, round_)


def delete_excel_files(location):
    """Delete all excel files related with the project once they are zipped."""
    shutil.rmtree(location)


def delete_zip_file(location):
    """Remove a zip file with user permission."""
    os.remove(location)


def convert_datetime(dt: str):
    """Convert a date time str representation to a python datetime object."""
    return datetime.strptime(dt, "%d/%m/%Y %H:%M:%S")


def check_extensions(ext):
    """Check if file extension is allowed."""
    if ext in SUPPORTED_FILES:
        return True
    else:
        return False


def config_from_file():
    """Open config file."""
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ROOT = Path(__file__).resolve().parent.parent
    with open(f"{ROOT}/config.json") as f:
        config = json.load(f)
    return config


def save_config_to_file(new_config):
    def string_to_int(value):
        """Convert config float type string into float type."""
        try:
            return int(value)
        except ValueError:
            return value.strip()

    config_keys = {
        "experiment_file_config": {},
        "file_cycle_config": {},
        "pump_control_config": {},
    }

    for k, v in new_config.items():
        if k.startswith("output_file"):
            k = k.replace("output_file_", "")
            config_keys["experiment_file_config"].update({k: v.strip()})
        elif k.startswith("pump"):
            k = k.replace("pump_", "")
            if k == "aqua_volume":
                config_keys["pump_control_config"].update({k: float(v)})
            config_keys["pump_control_config"].update({k: string_to_int(v)})

        elif k.startswith("file"):
            k = k.replace("file_", "")
            if k == "aqua_volume":
                config_keys["file_cycle_config"].update({k: float(v)})
            else:
                config_keys["file_cycle_config"].update({k: string_to_int(v)})
        else:
            if k not in ["save_loop_df", "save_converted"]:
                print(f"Unexpected value {k}: {v}")
    config_keys["experiment_file_config"].update(
        {"SAVE_LOOP_DF": True if new_config.get("save_loop_df") else False}
    )
    config_keys["experiment_file_config"].update(
        {"SAVE_CONVERTED": True if new_config.get("save_converted") else False}
    )

    with open("config.json", "w") as f:
        json.dump(config_keys, f)
    return config_keys


def progress_bar(func):
    """Decorates ``func`` to display a progress bar while running.

    The decorated function can yield values from 0 to 100 to
    display the progress.
    """

    def _func_with_progress(*args, **kwargs):
        max_width, _ = shutil.get_terminal_size()

        gen = func(*args, **kwargs)
        while True:
            try:
                progress = next(gen)
            except StopIteration as e:
                sys.stdout.write("\n")
                return e.value
            else:
                # Build the displayed message so we can compute
                # how much space is left for the progress bar itself.
                message = "[%s] {}%%".format(progress)
                # Add 3 characters to cope for the %s and %%
                bar_width = max_width - len(message) + 3

                filled = int(round(bar_width / 100.0 * progress))
                spaceleft = bar_width - filled
                bar = "=" * filled + " " * spaceleft
                sys.stdout.write((f"{message}\r") % bar)
                sys.stdout.flush()

    return _func_with_progress
