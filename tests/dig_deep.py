import pandas as pd
import datetime


def convert_datetime(dt: str):
    """Convert a date time str representation to a python datetime object."""
    try:
        return datetime.datetime.strptime(dt, "%d/%m/%Y %H:%M:%S")
    except ValueError:  # only for testing
        try:
            return datetime.datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        except ValueError:  # only for testing
            return datetime.datetime.strptime(dt, "%d/%m/%Y %H:%M")


C1 = "/home/somnium/Desktop/ANGULA/RealData/D3/C1.txt"
C2 = "/home/somnium/Desktop/ANGULA/RealData/D3/C2.txt"
file_path = "/home/somnium/Desktop/ANGULA/RealData/D3/Angula.txt"
flush, wait, close = 3, 10, 40

##################
# fileformat class
df = pd.read_table(C1, encoding="Windows-1252", decimal=",", low_memory=False)
col_idx = 8
df = df[col_idx:]
columns_name = list(df.iloc[0])[:6]
# Drop all NaN columns
df.dropna(axis=1, inplace=True)
# df = df.iloc[:, 0:6]
# Set new columns names
df.columns = columns_name
df.reset_index(inplace=True, drop=True)
df.drop(0, 0, inplace=True)  # remove the line were was the columns name

# Change date time column to a python datetime object
df.loc[:, "Date &Time [DD-MM-YYYY HH:MM:SS]"] = (
    df["Date &Time [DD-MM-YYYY HH:MM:SS]"].map(convert_datetime).copy()
)

self_df = df

#########
# experiment class
columns_columns = list(self_df.columns)
if "SDWA0003000061      , CH 1 temp [?C]" in self_df.columns:
    idx = columns_name.index("SDWA0003000061      , CH 1 temp [?C]")
    columns_name.remove("SDWA0003000061      , CH 1 temp [?C]")
    columns_name.insert(idx, "SDWA0003000061      , CH 1 temp [°C]")

self_df.columns = columns_name
df = self_df.copy()
