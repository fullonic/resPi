import time
import sys
sys.path.append("/home/somnium/Desktop/Projects/resPI/")
# import queue
# from threading import Thread

from scripts import Plot, ExperimentCycle, ControlFile, Control, ResumeDataFrame, FileFormater
from scripts.utils import string_to_float

# now = time.perf_counter()
C1 = "/home/somnium/Desktop/ANGULA/RealData/D3/control1.txt"
C2 = "/home/somnium/Desktop/ANGULA/RealData/D3/control2.txt"
file_path = "/home/somnium/Desktop/ANGULA/RealData/D3/Angula.txt"
dst = "/home/somnium/Desktop/ANGULA/RealData"
flush, wait, close = 3, 10, 40
#
for c in [C1, C2]:
    C = ControlFile(flush, wait, close, c, ignore_loops=[0])
    C_Total = Control(C)
    C_Total.get_bank()
control = C_Total.calculate_blank()
experiment = ExperimentCycle(flush, wait, close, file_path)
lst = experiment.df_close_list
len(lst)

# # experiment
# # experiment.create_plot()
#
print(control)
resume = ResumeDataFrame(experiment)
resume.generate_resume(control)
resume.save()

# f = FileFormater(C1)
# f.to_dataframe()


lst = ['Date &Time [DD-MM-YYYY HH:MM:SS]', 'Time stamp code',
       'Barometric pressure [hPa]', 'SDWA0003000061      , CH 1 phase [r.U.]',
       'SDWA0003000061      , CH 1 temp [°C]',
       'SDWA0003000061      , CH 1 O2 [mg/L]']

if "SDWA0003000061      , CH 1 temp [?C]" in lst:
    idx = lst.index("SDWA0003000061      , CH 1 temp [?C]")
    lst.remove("SDWA0003000061      , CH 1 temp [?C]")
    lst.insert(idx, "SDWA0003000061      , CH 1 temp [°C]")
