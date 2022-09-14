#!/usr/bin/env python3

import sys
import os
import subprocess


if 'BAK_CONFIGMAP' in os.environ:
    sys.path.insert(0, os.environ['BAK_CONFIGMAP'])
from clusterbuster_pod_client import clusterbuster_pod_client

client = clusterbuster_pod_client()
listen_port = client.command_line()[0]


def runit(client: clusterbuster_pod_client, process: int, *args):
    client.timestamp("Starting uperf server on port $listen_port")
    subprocess.run(['uperf', '-s', '-v', '-P', listen_port])
    client.timestamp("Done!")


client.run_workload(runit, initialize_timing_if_needed = False)
