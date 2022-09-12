#!/usr/bin/env python3

import sys
import os
import time
import signal

if 'BAK_CONFIGMAP' in os.environ:
    sys.path.insert(0, os.environ['BAK_CONFIGMAP'])
from clusterbuster_pod_client import clusterbuster_pod_client

client = clusterbuster_pod_client()
processes, memory, runtime = client.command_line()
processes = int(processes)
memory = int(memory)
runtime = float(runtime)


def runit():
    client.initialize_timing()

    user, system = client.cputimes()
    data_start_time = client.adjusted_time()
    memory_blk = 'a' * memory

    if runtime >= 0:
        time.sleep(runtime)
    else:
        signal.pause()

    user1, system1 = client.cputimes()
    data_end_time = client.adjusted_time()
    user1 -= user
    system1 -= system
    client.report_results(data_start_time, data_end_time, data_end_time - data_start_time, user, system)


client.run_workload(runit, processes)
