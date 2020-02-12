import time
import sys

sys.path.append("/home/somnium/Desktop/Projects/resPI/")
import pandas as pd

from scripts import Plot, ExperimentCycle, ControlFile, Control, ResumeDataFrame, FileFormater
from scripts.utils import string_to_float


def test_full_file_process(plot=False, save=False):
    now = time.perf_counter()
    C1 = "/home/somnium/Desktop/ANGULA/RealData/D3/C1.txt"
    C2 = "/home/somnium/Desktop/ANGULA/RealData/D3/C2.txt"
    file_path = "/home/somnium/Desktop/ANGULA/RealData/D3/Angula.txt"
    dst = "/home/somnium/Desktop/ANGULA/RealData/results"
    flush, wait, close = 3, 10, 40
    for c in [C1, C2]:
        C = ControlFile(flush, wait, close, c, ignore_loops=[0])
        C_Total = Control(C)
        C_Total.get_bank()
    control = C_Total.calculate_blank()
    experiment = ExperimentCycle(flush, wait, close, file_path)

    if plot:
        experiment.create_plot()
    resume = ResumeDataFrame(experiment)
    resume.generate_resume(control)
    if save:
        resume.save()
    print(time.perf_counter() - now)


test_full_file_process(plot=True, save=True)


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
