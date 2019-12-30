import os
import datetime

import pandas as pd
import random

from scripts.converter import FileFormater, ExperimentCycle
from scripts.stats import ResumeDataFrame

def fake_data():
    file_name = "/home/somnium/Desktop/angula5.txt"

    col = "SDWA0003000061      , CH 1 O2 [mg/L]"

    def loop():
        file_ = FileFormater(file_name)
        file_.to_dataframe()
        df = file_.df
        w = 25 * 60
        c = 20 * 60
        wast = w - c

        max_ = float(df[col].max().replace(",", "."))
        min_ = float(df[col].min().replace(",", "."))

        values_list = []
        for val in range(wast, w):
            values_list.append(random.uniform(min_, max_))

        lst = sorted(values_list)[::-1]
        lst.append(lst[-1])

        count = 0
        for i in range(wast, w + 1):
            df.loc[i, col] = lst[count]
            count += 1

        new_df = df[:w]

        return new_df

    frames = [loop() for i in range(6)]
    results = pd.concat(frames, ignore_index=True)
    # original df
    file_ = FileFormater(file_name)
    file_.to_dataframe()
    df = file_.df

    results = results[:len(df)]
    lst = list(results[col])
    df[col] = lst
    df.to_csv(f"{os.path.dirname(file_name)}/fake_data.txt", index=False, sep="\t")
    5*60
    df.iloc[299][col]


def fake_control():
    file_name = "/home/somnium/Desktop/angula5.txt"
    file_ = FileFormater(file_name)
    file_.to_dataframe()
    df = file_.df
    w = 25 * 60
    c = 20 * 60
    wast = w - c

    col = "SDWA0003000061      , CH 1 O2 [mg/L]"
    max_ = float(df[col].max().replace(",", "."))
    min_ = max_ - 0.2

    values_list = []
    for val in range(wast, w):
        values_list.append(random.uniform(min_, max_))

    lst = sorted(values_list)[::-1]
    lst.append(lst[-1])

    count = 0
    for i in range(wast, w + 1):
        df.loc[i, col] = lst[count]
        count += 1

    df_loop = df[:w]

    frames = [df_loop for i in range(1)]
    results = pd.concat(frames, ignore_index=True)
    return results

def create_config_file():
    import json

    config = {
        "experiment_file_config": {
            "DT_COL": "Date &Time [DD-MM-YYYY HH:MM:SS]",
            "TSCODE": "Time stamp code",
            "O2_COL": "SDWA0003000061      , CH 1 O2 [mg/L]",
            "PLOT_TITLE": "O2 Evo",
            "X_COL": "x",
            "Y_COL": "y",
            "SAVE_CONVERTED": True,
            "SAVE_LOOP_DF": True,
        },
        "file_cycle_config": {"flush": 3, "wait": 2, "close": 20, "aqua_volume": 21.0},
        "pump_control_config": {"flush": 3, "wait": 2, "close": 20, "aqua_volume": "40.434"},
    }
    with open("config.json", "w") as f:
        json.dump(config, f)


# create_config_file()
