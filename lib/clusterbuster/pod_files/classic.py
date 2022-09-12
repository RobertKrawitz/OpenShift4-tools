#!/usr/bin/env python3

import sys
import time
import os

if 'BAK_CONFIGMAP' in os.environ:
    sys.path.insert(0, os.environ['BAK_CONFIGMAP'])
from clusterbuster_pod_client import clusterbuster_pod_client

client = clusterbuster_pod_client()
sleep_time = float(client.command_line()[0])

def runit():
    client.timestamp(f"runit")
    client.initialize_timing()
    client.timestamp("Initialized timing")
    data_start_time = client.adjusted_time()
    client.timestamp(f"Got adjusted start time {data_start_time}")
    if sleep_time > 0:
        time.sleep(sleep_time)
    client.timestamp(f"Slept {sleep_time}")
    data_end_time = client.adjusted_time()
    client.timestamp(f"Got adjusted end time {data_start_time}")
    user, sys = client.cputime()
    client.timestamp(f"User, system CPU time {user} {sys}")
    client.report_results(data_start_time, data_end_time, data_end_time - data_start_time, user, sys)


client.run_workload(runit)
