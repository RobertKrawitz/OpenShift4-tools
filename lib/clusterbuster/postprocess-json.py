#!/usr/bin/python3

from __future__ import print_function
from pathlib import Path
import math
import re
import sys
import json

mode_func = None
rows = []
mode = None

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def efail(*args, **kwargs):
    eprint(args, kwargs)
    sys.exit(1)

def process_cpusoaker(rows):
    answer = {}
    answer['mode'] = 'cpu-soaker'
    answer['rows'] = []
    first_start = None
    last_start = None
    first_end = None
    last_end = None
    total_cpu = 0.0
    total_cpu_util = 0.0
    total_iterations = 0
    total_et = 0.0
    for row in rows:
        rowhash = {}
        rowhash['raw_result'] = row[0]
        rowhash['namespace'] = row[2]
        rowhash['pod'] = row[3]
        rowhash['container'] = row[5]
        rowhash['pid'] = row[12]
        rowhash['init_et'] = float(row[13])
        rowhash['container_start_relative'] = float(row[14])
        rowhash['run_start'] = float(row[15])
        rowhash['runtime'] = float(row[16])
        rowhash['run_end'] = float(row[17])
        rowhash['cpu_time'] = float(row[18])
        rowhash['cpu_util'] = float(row[19]) / 100.0
        rowhash['iterations'] = int(row[20])
        rowhash['iterations_per_sec'] = int(row[21])
        if first_start is None or rowhash['run_start'] < first_start:
            first_start = rowhash['run_start']
        if first_end is None or rowhash['run_end'] < first_end:
            first_end = rowhash['run_end']
        if last_start is None or rowhash['run_start'] > last_start:
            last_start = rowhash['run_start']
        if last_end is None or rowhash['run_end'] > last_end:
            last_end = rowhash['run_end']
        total_cpu += rowhash['cpu_time']
        total_cpu_util += rowhash['cpu_util']
        total_iterations += rowhash['iterations']
        total_et += rowhash['runtime']
        answer['rows'].append(rowhash)

    answer['summary'] = {}
    answer['summary']['first_run_start'] = first_start
    answer['summary']['first_run_end'] = first_end
    answer['summary']['last_run_start'] = last_start
    answer['summary']['last_run_end'] = last_end
    answer['summary']['total_iterations'] = total_iterations
    if total_cpu > 0:
        answer['summary']['iterations_per_cpu_sec'] = round(total_iterations / total_cpu, 3)
    else:
        answer['summary']['iterations_per_cpu_sec'] = 0.0
    if total_et > 0:
            answer['summary']['iterations_per_sec'] = round(total_iterations / total_et, 3)
    else:
        answer['summary']['iterations_per_sec'] = 0.0
    answer['summary']['elapsed_time_average'] = round(total_et / len(rows), 3)
    answer['summary']['elapsed_time_net'] = round(last_end - first_start, 3)
    answer['summary']['overlap_error'] = round((((last_start - first_start) +
                                                 (last_end - first_end)) / 2) /
                                               (total_et / len(rows)), 5)
    answer['summary']['total_cpu_utilization'] = round(total_cpu_util, 5)
    return answer

def postprocess_clientserver(rows):
    answer = {}
    answer['mode'] = 'cpu-soaker'
    answer['rows'] = []
    total_max_round_trip_time = 0
    round_trip_time_accumulator = 0
    total_data_rate = 0
    total_date_xfer = 0
    total_iterations = 0
    for row in rows:
        rowhash = {}
        rowhash['raw_result'] = row[0]
        rowhash['namespace'] = row[2]
        rowhash['pod'] = row[3]
        rowhash['container'] = row[5]
        rowhash['pid'] = row[12]
        rowhash['run_start'] = float(row[15])
        rowhash['runtime'] = float(row[21])
        rowhash['run_end'] = float(row[16])
        rowhash['mean_round_trip_time'] = float(row[23])
        rowhash['max_round_trip_time'] = float(row[24])
        rowhash['iterations'] = int(row[27])
        rowhash['data_xfer'] = int(row[20])
        rowhash['data_rate'] = round(rowhash['data_xfer'] / rowhash['runtime'])
        if first_start is None or rowhash['run_start'] < first_start:
            first_start = rowhash['run_start']
        if first_end is None or rowhash['run_end'] < first_end:
            first_end = rowhash['run_end']
        if last_start is None or rowhash['run_start'] > last_start:
            last_start = rowhash['run_start']
        if last_end is None or rowhash['run_end'] > last_end:
            last_end = rowhash['run_end']
        if rowhash['mean_round_trip_time'] > total_max_round_trip_time:
            total_max_round_trip_time = rowhash['mean_round_trip_time']
        total_data_xfer += rowhash['data_xfer']
        total_iterations += rowhash['iterations']
        total_et += rowhash['runtime']
        round_trip_time_accumulator += rowhash['mean_round_trip_time']
        answer['rows'].append(rowhash)

    answer['summary'] = {}
    answer['summary']['first_run_start'] = first_start
    answer['summary']['first_run_end'] = first_end
    answer['summary']['last_run_start'] = last_start
    answer['summary']['last_run_end'] = last_end
    answer['summary']['total_iterations'] = total_iterations
    answer['summary']['elapsed_time_average'] = round(total_et / len(rows), 3)
    answer['summary']['elapsed_time_net'] = round(last_end - first_start, 3)
    answer['summary']['overlap_error'] = round((((last_start - first_start) +
                                                 (last_end - first_end)) / 2) /
                                               (total_et / len(rows)), 5)
    answer['summary']['total_iterations'] = total_iterations
    answer['summary']['max_round_trip_time'] = total_max_round_trip_time
    answer['summary']['total_data_xfer'] = total_data_xfer
    answer['summary']['average_round_trip_time'] = round(round_trip_time_accumulator / len(rows), 6)
    return answer

def postprocess_clientserver(rows):
    efail("Not yet implemented")

def postprocess_sysbench(rows):
    efail("Not yet implemented")

for line in sys.stdin:
    line = line.rstrip()
    vals = [line]
    vals.extend(line.split(','))
    if mode is None:
        if re.compile(r'-soaker-').search(vals[3]):
            mode_func = process_cpusoaker
        elif re.compile(r'-client-').search(vals[3]):
            mode_func = process_clientserver
        elif re.compile(r'-sysbench-').search(vals[3]):
            mode_func = process_sysbench
        elif re.compile(r'-files-').search(vals[3]):
            mode_func = process_files
        else:
            efail("Unrecognized mode from %s" % (vals[3]), file=sys.stderr)
    vals.insert(0, line)
    rows.append(vals)

if mode_func is not None:
    print(json.dumps(mode_func(rows)))
