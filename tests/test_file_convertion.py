import time
import sys
from pathlib import Path

sys.path.append("/home/somnium/Desktop/Projects/resPI/")
import pandas as pd

from scripts import (
    Plot,
    ExperimentCycle,
    ControlFile,
    ResumeControl,
    ResumeDataFrame,
    FileFormater,
)
from scripts.utils import string_to_float, global_plots


def test_full_file_process(plot=False, save=False):
    now = time.perf_counter()
    C1 = "/home/somnium/Desktop/ANGULA/RealData/D3/C1.txt"
    C2 = "/home/somnium/Desktop/ANGULA/RealData/D3/C2.txt"
    data_file = "/home/somnium/Desktop/ANGULA/RealData/D3/Angula.txt"
    dst = "/home/somnium/Desktop/ANGULA/RealData/results"
    # ignore_loops = {"C2": ["2", "3"], "Data": [], "C1": ["1"]}
    ignore_loops = {"C2": [], "Data": ["1", "2"], "C1": []}
    flush, wait, close = 3, 10, 40
    for idx, c in enumerate([C1, C2]):
        C = ControlFile(
            flush,
            wait,
            close,
            c,
            file_type=f"control_{idx+1}",
            ignore_loops=ignore_loops,
        )
        C_Total = ResumeControl(C)
        # C_Total.generate_resume(0)
        # C_Total.save()
        C_Total.get_bank()
    control = C_Total.calculate_blank()

    experiment = ExperimentCycle(
        flush, wait, close, data_file, file_type="data", ignore_loops=ignore_loops
    )

    resume = ResumeDataFrame(experiment)
    resume.generate_resume(control)
    if plot:
        experiment.create_plot()
        C.create_plot()
        global_plots(
            flush,
            wait,
            close,
            [C1, data_file, C2],
            preview_folder="/home/somnium/Desktop/Projects/resPI/templates/previews",
            keep=True,
            folder_dst=resume.experiment.original_file.folder_dst,
        )
    if save:
        resume.save()
    # resume.zip_folder()
    print(time.perf_counter() - now)
    # for f in Path("/home/somnium/Desktop/ANGULA/RealData/D3/").glob("*.xlsx"):
    #     f.unlink()


# -0.1195239775296602
########
# Test plot
########
def get_trend_plot_data():
    x_axis = "Temps (Hr)"
    y_axis = "mg 02/L"
    data = pd.read_excel("/home/somnium/Desktop/ANGULA/TESTDATA/df_loop_1.xlsx")
    title = "test"
    dst = "/home/somnium/Desktop/ANGULA/TESTDATA/"
    plot = Plot(data, x_axis, y_axis, title, dst=dst)
    p = plot.create()

    # dir(p.data[1])
    p.data[1].hovertemplate


def test_route_upload():
    pass


test_full_file_process(plot=True, save=True)
# -0.1195239775296602
