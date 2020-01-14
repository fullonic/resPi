import time

# import queue
# from threading import Thread

from scripts import Plot, ExperimentCycle, ControlFile, Control, ResumeDataFrame
from scripts.utils import string_to_float

now = time.perf_counter()
C1 = "/home/somnium/Desktop/ANGULA/RealData/C2.txt"
C2 = "/home/somnium/Desktop/ANGULA/RealData/C2.txt"
file_path = "/home/somnium/Desktop/ANGULA/RealData/n1.txt"
dst = "/home/somnium/Desktop/ANGULA/RealData"
flush, wait, close = 3, 6, 30

for c in [C1, C2]:
    C = ControlFile(flush, wait, close, c)
    C_Total = Control(C)
    C_Total.get_bank()
control = C_Total.calculate_blank()
experiment = ExperimentCycle(flush, wait, close, file_path)
experiment.create_plot()
resume = ResumeDataFrame(experiment)
resume.generate_resume(control)
# resume.save()
