#!/usr/bin/env python3

import sys
import os
import time

if 'BAK_CONFIGMAP' in os.environ:
    sys.path.insert(0, os.environ['BAK_CONFIGMAP'])
from clusterbuster_pod_client import clusterbuster_pod_client

client = clusterbuster_pod_client()
sync_count, sync_cluster_count, sync_sleep, processes = client.command_line()
sync_count = int(sync_count)
sync_cluster_count = int(sync_cluster_count)
sync_sleep = float(sync_sleep)
processes = int(processes)


def runit(client: clusterbuster_pod_client, process: int, *args):
    user, system = client.cputimes()
    data_start_time = client.adjusted_time()
    for i in range(sync_count):
        for j in range(sync_cluster_count):
            client.sync_to_controller(client.idname([i, j]))
        if sync_sleep > 0:
            time.sleep(sync_sleep)
    user, system = client.cputimes(user, system)
    data_end_time = client.adjusted_time()
    client.report_results(data_start_time, data_end_time, data_end_time - data_start_time, user, system)


client.run_workload(runit, processes)
