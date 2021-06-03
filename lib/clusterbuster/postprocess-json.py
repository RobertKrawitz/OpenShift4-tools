#!/usr/bin/python3

from __future__ import print_function
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
        rowhash['init_et'] = float(row[13])
        rowhash['container_start_relative'] = float(row[14])
        rowhash['run_start'] = float(row[14])
        rowhash['runtime'] = float(row[15])
        rowhash['run_end'] = float(row[16])
        rowhash['cpu_time'] = float(row[17])
        rowhash['cpu_util'] = float(row[18]) / 100.0
        rowhash['iterations'] = int(row[19])
        rowhash['iterations_per_sec'] = float(row[20])
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

    summary = {}
    answer['summary'] = summary
    summary['total_iterations'] = total_iterations
    if total_cpu > 0:
        summary['iterations_per_cpu_sec'] = round(total_iterations / total_cpu, 3)
    else:
        summary['iterations_per_cpu_sec'] = 0.0
    if total_et > 0:
        summary['iterations_per_sec'] = round(total_iterations / (last_end - first_start), 3)
    else:
        summary['iterations_per_sec'] = 0.0
    summary['elapsed_time_average'] = round(total_et / len(rows), 3)
    summary['elapsed_time_net'] = round(last_end - first_start, 3)
    summary['overlap_error'] = round((((last_start - first_start) +
                                       (last_end - first_end)) / 2) /
                                     (total_et / len(rows)), 5)
    summary['total_cpu_time'] = round(total_cpu, 3)
    summary['total_cpu_utilization'] = round(total_cpu_util, 5)
    return answer


def process_clientserver(rows):
    answer = {}
    answer['mode'] = 'clientserver'
    answer['rows'] = []
    total_max_round_trip_time = 0
    round_trip_time_accumulator = 0
    total_data_xfer = 0
    total_iterations = 0
    total_et = 0.0
    first_start = None
    last_start = None
    first_end = None
    last_end = None
    for row in rows:
        rowhash = {}
        rowhash['raw_result'] = row[0]
        rowhash['namespace'] = row[2]
        rowhash['pod'] = row[3]
        rowhash['container'] = row[5]
#        rowhash['pid'] = row[12]
        rowhash['run_start'] = float(row[15])
        rowhash['runtime'] = float(row[21])
        rowhash['run_end'] = float(row[16])
        rowhash['mean_round_trip_time'] = float(row[23])
        rowhash['max_round_trip_time'] = float(row[24])
        rowhash['iterations'] = int(row[9])
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
        if rowhash['max_round_trip_time'] > total_max_round_trip_time:
            total_max_round_trip_time = rowhash['max_round_trip_time']
        total_data_xfer += rowhash['data_xfer']
        total_iterations += rowhash['iterations']
        total_et += rowhash['runtime']
        round_trip_time_accumulator += rowhash['mean_round_trip_time']
        answer['rows'].append(rowhash)

    summary = {}
    answer['summary'] = summary
    summary['first_run_start'] = first_start
    summary['first_run_end'] = first_end
    summary['last_run_start'] = last_start
    summary['last_run_end'] = last_end
    summary['total_iterations'] = total_iterations
    summary['elapsed_time_average'] = round(total_et / len(rows), 3)
    summary['elapsed_time_net'] = round(last_end - first_start, 3)
    summary['overlap_error'] = round((((last_start - first_start) +
                                       (last_end - first_end)) / 2) /
                                     (total_et / len(rows)), 5)
    summary['total_iterations'] = total_iterations
    summary['max_round_trip_time_msec'] = total_max_round_trip_time
    summary['total_data_xfer_bytes'] = total_data_xfer
    summary['average_data_rate_bytes_sec'] = round(total_data_xfer / (last_end - first_start), 0)
    summary['average_round_trip_time_msec'] = round(round_trip_time_accumulator / len(rows), 6)
    summary['total_clients'] = len(rows)
    return answer


def process_files(rows):
    answer = {}
    answer['mode'] = 'files'
    answer['rows'] = []

    first_start = None
    last_start = None
    first_end = None
    last_end = None
    total_runtime = 0.0

    create_first_start = None
    create_first_end = None
    create_last_start = None
    create_last_end = None

    remove_first_start = None
    remove_first_end = None
    remove_last_start = None
    remove_last_end = None

    create_elapsed = 0.0
    create_ops = 0
    create_user_cpu = 0.0
    create_sys_cpu = 0.0
    create_total_cpu = 0.0

    remove_elapsed = 0.0
    remove_ops = 0
    remove_user_cpu = 0.0
    remove_sys_cpu = 0.0
    remove_total_cpu = 0.0
    for row in rows:
        rowhash = {}
        rowhash['raw_result'] = row[0]
        rowhash['namespace'] = row[2]
        rowhash['pod'] = row[3]
        rowhash['container'] = row[5]

        rowhash['create_start'] = float(row[17])
        rowhash['create_et'] = float(row[18])
        rowhash['create_end'] = rowhash['create_start'] + rowhash['create_et']
        rowhash['create_user_cpu'] = float(row[19])
        rowhash['create_sys_cpu'] = float(row[20])
        rowhash['create_total_cpu'] = rowhash['create_user_cpu'] + rowhash['create_sys_cpu']
        rowhash['create_ops'] = float(row[22])
        create_ops += rowhash['create_ops']
        create_user_cpu += rowhash['create_user_cpu']
        create_sys_cpu += rowhash['create_sys_cpu']
        create_total_cpu += create_user_cpu + create_sys_cpu
        create_elapsed += rowhash['create_et']
        if create_first_start is None or rowhash['create_start'] < create_first_start:
            create_first_start = rowhash['create_start']
        if create_first_end is None or rowhash['create_end'] < create_first_end:
            create_first_end = rowhash['create_end']
        if create_last_start is None or rowhash['create_start'] > create_last_start:
            create_last_start = rowhash['create_start']
        if create_last_end is None or rowhash['create_end'] > create_last_end:
            create_last_end = rowhash['create_end']

        rowhash['remove_start'] = float(row[26])
        rowhash['remove_et'] = float(row[27])
        rowhash['remove_end'] = round(rowhash['remove_start'] + rowhash['remove_et'], 3)
        rowhash['remove_user_cpu'] = float(row[28])
        rowhash['remove_sys_cpu'] = float(row[29])
        rowhash['remove_total_cpu'] = rowhash['remove_user_cpu'] + rowhash['remove_sys_cpu']
        rowhash['remove_ops'] = float(row[31])
        remove_ops += rowhash['remove_ops']
        remove_user_cpu += rowhash['remove_user_cpu']
        remove_sys_cpu += rowhash['remove_sys_cpu']
        remove_total_cpu += remove_user_cpu + remove_sys_cpu
        remove_elapsed += rowhash['remove_et']
        if remove_first_start is None or rowhash['remove_start'] < remove_first_start:
            remove_first_start = rowhash['remove_start']
        if remove_first_end is None or rowhash['remove_end'] < remove_first_end:
            remove_first_end = rowhash['remove_end']
        if remove_last_start is None or rowhash['remove_start'] > remove_last_start:
            remove_last_start = rowhash['remove_start']
        if remove_last_end is None or rowhash['remove_end'] > remove_last_end:
            remove_last_end = rowhash['remove_end']

        rowhash['run_start'] = float(row[12])
        rowhash['runtime'] = float(row[13])
        total_runtime += rowhash['runtime']
        rowhash['run_end'] = rowhash['run_start'] + rowhash['runtime']
        if first_start is None or rowhash['run_start'] < first_start:
            first_start = rowhash['run_start']
        if first_end is None or rowhash['run_end'] < first_end:
            first_end = rowhash['run_end']
        if last_start is None or rowhash['run_start'] > last_start:
            last_start = rowhash['run_start']
        if last_end is None or rowhash['run_end'] > last_end:
            last_end = rowhash['run_end']

        rowhash['total_user_cpu'] = rowhash['create_user_cpu'] + rowhash['remove_user_cpu']
        rowhash['total_sys_cpu'] = rowhash['create_sys_cpu'] + rowhash['remove_sys_cpu']
        rowhash['total_cpu'] = rowhash['total_user_cpu'] + rowhash['total_sys_cpu']
        rowhash['total_ops'] = rowhash['create_ops'] + rowhash['remove_ops']
        answer['rows'].append(rowhash)

    summary = {}
    answer['summary'] = summary

    summary['first_run_start'] = round(first_start, 3)
    summary['first_run_end'] = round(first_end, 3)
    summary['last_run_start'] = round(last_start, 3)
    summary['last_run_end'] = round(last_end, 3)
    summary['elapsed_time_average'] = round(total_runtime / len(rows), 3)
    summary['elapsed_time_net'] = round(last_end - first_start, 3)
    summary['overlap_error'] = round((((last_start - first_start) +
                                       (last_end - first_end)) / 2) /
                                     (total_runtime / len(rows)), 5)

    summary['create_ops'] = create_ops
    summary['create_elapsed'] = round(create_last_end - create_first_start, 3)
    summary['create_user_cpu'] = round(create_user_cpu, 3)
    summary['create_sys_cpu'] = round(create_sys_cpu, 3)
    summary['create_total_cpu'] = round(create_user_cpu + create_sys_cpu, 3)
    summary['create_cpu_utilization'] = round((create_user_cpu + create_total_cpu) / create_elapsed, 3)
    summary['create_ops'] = create_ops
    summary['create_ops_sec'] = round(create_ops / (create_last_end - create_first_start), 3)
    summary['create_overlap_error'] = round((((create_last_start - create_first_start) +
                                              (create_last_end - create_first_end)) / 2) /
                                            (create_elapsed / len(rows)), 5)

    summary['remove_ops'] = remove_ops
    summary['remove_elapsed'] = round(remove_last_end - remove_first_start, 3)
    summary['remove_user_cpu'] = round(remove_user_cpu, 3)
    summary['remove_sys_cpu'] = round(remove_sys_cpu, 3)
    summary['remove_total_cpu'] = round(remove_user_cpu + remove_sys_cpu, 3)
    summary['remove_cpu_utilization'] = round(summary['remove_total_cpu'] / summary['remove_elapsed'], 3)
    summary['remove_ops'] = remove_ops
    summary['remove_ops_sec'] = round(remove_ops / (remove_last_end - remove_first_start), 3)
    summary['remove_overlap_error'] = round((((remove_last_start - remove_first_start) +
                                              (remove_last_end - remove_first_end)) / 2) /
                                            (remove_elapsed / len(rows)), 5)

    summary['total_ops'] = create_ops + remove_ops
    summary['total_elapsed'] = round(summary['create_elapsed'] + summary['remove_elapsed'], 3)
    summary['total_user_cpu'] = round(create_user_cpu + remove_user_cpu, 3)
    summary['total_sys_cpu'] = round(create_sys_cpu + remove_sys_cpu, 3)
    summary['total_cpu'] = round(create_user_cpu + remove_user_cpu + create_sys_cpu + remove_sys_cpu, 3)
    summary['total_cpu_utilization'] = round(summary['total_cpu'] / summary['total_elapsed'], 3)
    summary['total_ops'] = create_ops + remove_ops
    summary['total_ops_sec'] = round((create_ops + remove_ops) /
                                     ((create_last_end - create_first_start) +
                                      (remove_last_end - remove_last_start)), 3)
    return answer


def process_sysbench(rows):
    answer = {}
    answer['mode'] = 'cpu-soaker'
    answer['rows'] = []
    first_start = None
    last_start = None
    first_end = None
    last_end = None
    read_rate = 0.0
    write_rate = 0.0
    read_ops = 0
    write_ops = 0
    fsync_ops = 0
    for row in rows:
        rowhash = {}
        rowhash['raw_result'] = row[0]
        rowhash['namespace'] = row[2]
        rowhash['pod'] = row[3]
        rowhash['container'] = row[5]
        rowhash['run_start'] = float(row[12])
        rowhash['runtime'] = float(row[20])
        rowhash['run_end'] = float(row[14])
        if first_start is None or rowhash['run_start'] < first_start:
            first_start = rowhash['run_start']
        if first_end is None or rowhash['run_end'] < first_end:
            first_end = rowhash['run_end']
        if last_start is None or rowhash['run_start'] > last_start:
            last_start = rowhash['run_start']
        if last_end is None or rowhash['run_end'] > last_end:
            last_end = rowhash['run_end']
        rowhash['read_ops_sec'] = int(row[15])
        rowhash['write_ops_sec'] = int(row[16])
        rowhash['fsync_ops_sec'] = int(row[17])
        rowhash['read_rate_mbyte_sec'] = int(row[18])
        rowhash['write_rate_mbyte_sec'] = int(row[19])
        read_ops += rowhash['read_ops_sec']
        write_ops += rowhash['write_ops_sec']
        fsync_ops += rowhash['fsync_ops_sec']
        read_rate += rowhash['read_rate_mbyte_sec']
        write_rate += rowhash['write_rate_mbyte_sec']
        answer['rows'].append(rowhash)

    summary = {}
    answer['summary'] = summary
    summary['read_ops_sec'] = read_ops
    summary['write_ops_sec'] = write_ops
    summary['fsync_ops_sec'] = write_ops
    summary['read_rate_mbyte_sec'] = read_rate
    summary['write_rate_mbyte_sec'] = write_rate
    return answer


for line in sys.stdin:
    line = line.rstrip()
    vals = [line]
    splitchar = ','
    if line.find(",") == -1:
        splitchar = ' '
    vals.extend(line.split(splitchar))
    if mode is None and len(vals) > 3:
        if vals[3].find('-soaker-') >= 0:
            mode_func = process_cpusoaker
        elif vals[3].find('-client-') >= 0:
            mode_func = process_clientserver
        elif vals[3].find('-sysbench-') >= 0:
            mode_func = process_sysbench
        elif vals[3].find('-files-') >= 0:
            mode_func = process_files
        else:
            efail("Unrecognized mode from %s" % (vals[3]), file=sys.stderr)
    rows.append(vals)

if mode_func is not None:
    print(json.dumps(mode_func(rows)))
