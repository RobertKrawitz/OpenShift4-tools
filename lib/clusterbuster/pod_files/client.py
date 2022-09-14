#!/usr/bin/env python3

import sys
import os
import time
import random
import math

if 'BAK_CONFIGMAP' in os.environ:
    sys.path.insert(0, os.environ['BAK_CONFIGMAP'])
from clusterbuster_pod_client import clusterbuster_pod_client

client = clusterbuster_pod_client()
srvhost, connect_port, data_rate, nbytes, bytes_max, msg_size, xfertime, xfertime_max = client.command_line()
connect_port = int(connect_port)
data_rate = float(data_rate)
nbytes = int(nbytes)
bytes_max = int(bytes_max)
msg_size = int(msg_size)
xfertime = int(xfertime)
xfertime_max = int(xfertime_max)
verbose = client.verbose()
verbose = True


def runit(client: clusterbuster_pod_client, process: int, *args):

    npass = 0
    ex = 0
    ex2 = 0

    conn = client.connect_to(srvhost, connect_port)
    msg = ('A' * msg_size).encode()

    data_sent = 0
    mean_latency = 0
    max_latency = 0
    stdev_latency = 0

    global nbytes
    global xfertime
    if nbytes != bytes_max:
        nbytes += random.randint(0, bytes_max - nbytes)
    if xfertime != xfertime_max:
        xfertime += random.randint(0, xfertime_max - xfertime)

    user, system = client.cputimes()
    data_start_time = client.adjusted_time()
    time_overhead = client.calibrate_time()
    starttime = data_start_time
    while (nbytes > 0 and data_sent < bytes) or (xfertime > 0 and client.adjusted_time() - data_start_time < xfertime):
        rtt_start = client.adjusted_time()
        nleft = msg_size
        while nleft > 0:
            try:
                nwrite = conn.send(msg[(msg_size - nleft):])
            except Exception as error:
                client.timestamp(f"Write failed: {error}")
                return 1
            if nwrite > 0:
                nleft -= nwrite
                data_sent += nwrite
            else:
                client.timestamp("Unexpected zero length msg sent")
                return 1
        nleft = msg_size
        read_failures = 0
        while nleft > 0:
            try:
                answer = conn.recv(nleft)
            except Exception as error:
                client.timestamp(f"Read failed: {error}")
                if read_failures > 2:
                    return 1
                else:
                    read_failures += 1
                    continue
            nread = len(answer)
            read_failures = 0
            if nread > 0:
                nleft -= nread
            else:
                client.timestamp("Unexpected zero length msg received")
                return 1
        en = client.adjusted_time() - rtt_start - time_overhead
        ex += en
        ex2 += en * en
        if en > max_latency:
            max_latency = en
        if verbose:
            client.timestamp('Write/Read %d %.6f' % (msg_size, en))
        curtime = client.adjusted_time()
        if data_rate > 0:
            starttime += msg_size / data_rate
            if curtime < starttime:
                if verbose:
                    client.timestamp('Sleeping %8.6f', starttime - curtime)
                time.sleep(starttime - curtime)
            else:
                if verbose:
                    client.timestamp('Not sleeping')
        npass += 1
    data_end_time = client.adjusted_time()
    if npass > 0:
        mean_latency = ex / npass
        if npass > 1:
            stdev_latency = math.sqrt((ex2 - (ex * ex / npass)) / (npass - 1))

    user1, system1 = client.cputimes()
    user1 -= user
    system1 -= system
    elapsed_time = data_end_time - data_start_time
    if elapsed_time <= 0:
        elapsed_time = 0.00000001
    extra = {
        'data_sent_bytes': data_sent,
        'mean_latency_sec': mean_latency,
        'max_latency_sec': max_latency,
        'stdev_latency_sec': stdev_latency,
        'timing_overhead_sec': time_overhead,
        'target_data_rate': data_rate,
        'passes': npass,
        'msg_size': msg_size
    }
    client.report_results(data_start_time, data_end_time, data_end_time - data_start_time, user, system, extra)


client.run_workload(runit)
