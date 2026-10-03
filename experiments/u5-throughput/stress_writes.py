"""Run the pilot with deliberately slow fsync to exercise prefetch durability."""
import os
import time
import pilot

original_fsync=os.fsync
def slow_fsync(fd):
    time.sleep(0.03)
    original_fsync(fd)
os.fsync=slow_fsync
pilot.main()
