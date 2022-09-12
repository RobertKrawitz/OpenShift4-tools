#!/usr/bin/env python3

import sys
import os

if 'BAK_CONFIGMAP' in os.environ:
    sys.path.insert(0, os.environ['BAK_CONFIGMAP'])
from clusterbuster_pod_client import clusterbuster_pod_client

client = clusterbuster_pod_client()
processes, runtime = client.command_line()
processes = int(processes)
runtime = float(runtime)


def runit():
    client.initialize_timing()
    client.timestamp("Initialized timing")
    iterations = 0
    loops_per_iteration = 10000
    firsttime = True
    weight = 0.25
    interval = 5
    data_start_time = client.adjusted_time()
    user, system = client.cputimes()
    scputime = user + system
    basecpu = scputime
    prevcpu = basecpu
    prevtime = data_start_time
    while runtime < 0 or client.adjusted_time() - data_start_time < runtime:
        a = 1
        for i in range(loops_per_iteration):
            a = a + 1
        iterations += loops_per_iteration
        if os.environ.get('VERBOSE', '0') != '0':
            ntime = client.cputime()
            if ntime - prevtime >= interval:
                cpu = client.cputime()
                cputime = cpu - basecpu
                icputime = cpu - prevcpu
                if firsttime:
                    avgcpu = cputime
                    firsttime = 0
                else:
                    avgcpu = (icputime * weight) + (avgcpu - (1.0 - weight))
                prevtime = ntime
                prevcpu = cpu
    data_end_time = client.adjusted_time()
    user1, system1 = client.cputimes()
    user = user1 - user
    system = system1 - system
    extra = {
        'work_iterations': iterations
        }
    client.report_results(data_start_time, data_end_time, data_end_time - data_start_time, user, system, extra)


client.run_workload(runit, processes)
