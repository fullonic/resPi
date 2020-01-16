import time

# import queue
# from threading import Thread

from scripts import Plot, ExperimentCycle, ControlFile, Control, ResumeDataFrame, FileFormater
from scripts.utils import string_to_float

# now = time.perf_counter()
C1 = "/home/somnium/Desktop/ANGULA/RealData/D2/blanc16.txt"
C2 = "/home/somnium/Desktop/ANGULA/RealData/D2/blanc16.txt"
file_path = "/home/somnium/Desktop/ANGULA/RealData/D2/nitota.txt"
dst = "/home/somnium/Desktop/ANGULA/RealData"
flush, wait, close = 3, 10, 40
#
for c in [C1, C2]:
    C = ControlFile(flush, wait, close, c)
    C_Total = Control(C)
    C_Total.get_bank()
control = C_Total.calculate_blank()
experiment = ExperimentCycle(flush, wait, close, file_path)
# experiment
# experiment.create_plot()

print(control)
resume = ResumeDataFrame(experiment)
resume.generate_resume(control)
resume.save()

# f = FileFormater(C1)
# f.to_dataframe()
