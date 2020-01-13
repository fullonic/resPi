"""Main test for app."""
import os

from scripts import Plot, FileFormater, ExperimentCycle, ResumeDataFrame

# Variables
data = "/home/somnium/Desktop/Projects/resPI/tests/data/fake_cycle.txt"
C1 = "/home/somnium/Desktop/Projects/resPI/tests/data/control_file_1.txt"
C2 = "/home/somnium/Desktop/Projects/resPI/tests/data/control_file_2.txt"
flush, wait, close = 3, 2, 20
plot = True

experiment = ExperimentCycle(flush, wait, close, data)

resume = ResumeDataFrame(experiment)
resume.generate_resume(0.2)
resume.df_lists
p = Plot(
    resume.df_lists, "x", "y", "test", dst=os.path.dirname(experiment.original_file.file_output)
).create()
