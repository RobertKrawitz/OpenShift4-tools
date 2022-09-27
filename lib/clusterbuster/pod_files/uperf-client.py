#!/usr/bin/env python3

import os
import subprocess
import re
import json
import traceback

from clusterbuster_pod_client import clusterbuster_pod_client


class uperf_client(clusterbuster_pod_client):
    """
    uperf test for clusterbuster
    """

    def __init__(self):
        super().__init__()
        self.runtime = int(self._args[0])
        self.ramp_time = int(self._args[1])
        self.srvhost = self.resolve_host(self._args[2])
        self.connect_port = int(self._args[3])
        self.tests = self._args[4:]
        self.podfile_dir = os.environ.get('PODFILE_DIR', '.')
        self.process_file(os.path.join(self.podfile_dir, "uperf-mini.xml"), "/tmp/uperf-test.xml", {'srvhost': self.srvhost, 'runtime': 1})
        self.timestamp(f"Waiting for uperf server {self.srvhost}:{self.connect_port} to come online...")
        subprocess.run(f'until uperf -P "{self.connect_port}" -m /tmp/uperf-test.xml; do sleep 1; done', shell=True)
        self.timestamp("Connected to uperf server")

    def compute_seconds_uperf(self, value: str):
        # Specific to uperf, which defaults to milliseconds
        m = re.match(r'([0-9]+(\.[0-9]*)?)(ns|us|ms|s)$', value)
        if m:
            base = float(m.group(1))
            modifier = m.group(3)
            if modifier == 'us':
                return base / 1000000
            elif modifier == 'ns':
                return base / 1000000000
            elif modifier == 's':
                return base
            else:
                return base / 1000
        else:
            return None

    def process_file(self, infile: str, outfile: str, options: dict):
        with open(infile, 'r') as indata:
            contents = indata.read()
        for key, sub in options.items():
            contents = contents.replace(f"%{{{key}}}", str(sub))
        with open(outfile, 'w') as outdata:
            outdata.write(contents)

    def runit(self, process: int):
        ucpu, scpu = self.cputimes()
        counter = 1
        data_start_time = None
        failed_cases = []
        results = dict()
        cases = dict()
        elapsed_time = 0
        for test in self.tests:
            [test_type, proto, size, nthr] = re.split(r'[,\s]+', test)
            size = int(size)
            nthr = int(nthr)
            base_test_name = f"{proto}-{test_type}-{size}B-{nthr}i"
            options = {
                'srvhost': self.srvhost,
                'proto': proto,
                'test_type': test_type,
                'size': size,
                'runtime': self.runtime + (2 * self.ramp_time),
                'nthr': nthr
                }
            test_template = os.path.join(self.podfile_dir, f"uperf-{test_type}.xml")
            testfile = "/tmp/uperf-test.xml"
            self.process_file(test_template, testfile, options)
            test_name = '%04i-%s' % (counter, base_test_name)
            metadata = {
                'protocol': proto,
                'test_type': test_type,
                'message_size': size,
                'thread_count': nthr,
                'test_name': test_name
                }
            failed = False
            self.sync_to_controller(self.idname(test_name))
            self.timestamp(f"Running test {test_name}")
            with open(testfile, 'r') as f:
                self.timestamp(f.read())
            job_start_time = self.adjusted_time()
            if data_start_time is None:
                data_start_time = job_start_time
            with subprocess.Popen(["uperf", "-f", "-P", str(self.connect_port), '-m', '/tmp/uperf-test.xml', '-R', '-a', '-i', '1', '-Tf'], stdout = subprocess.PIPE) as run:
                first_time = 0
                last_time = 0
                last_nbytes = 0
                last_nops = 0
                timeseries = []
                threads = dict()
                summary = {
                    'write': {},
                    'read': {},
                    'total': {}
                    }
                failure_message = ''
                line = run.stdout.readline().decode('ascii')
                while line:
                    line = line.strip()
                    m = re.match(r'timestamp_ms:([0-9.]+) +name:([0-9a-zA-Z]+) +nr_bytes:([0-9]+) +nr_ops:([0-9]+)', line)
                    if m:
                        ts = float(m.group(1)) / 1000.0
                        name = m.group(2)
                        nbytes = int(m.group(3))
                        nops = int(m.group(4))
                        # We only care about Txn2 and threads; the other transactions are start
                        # and finish, and we want to ignore those
                        if name == 'Txn2':
                            row = {
                                'time': ts - first_time,
                                'timedelta': ts - last_time,
                                'nbytes': nbytes - last_nbytes,
                                'nops': nops - last_nops
                                }
                            timeseries.append(row)
                            last_time = ts
                            last_nbytes = nbytes
                            last_nops = nops
                        elif re.match(r'Thr([0-9]+)', name):
                            row = {
                                'time': ts - first_time,
                                'nbytes': nbytes,
                                'nops': nops
                                }
                            threads[name] = row
                    elif re.match(r'(Txn1|write|read)\s', line):
                        [op, count, avg, cpu, maximum, minimum] = line.split()
                        if op == 'Txn1':
                            op = 'total'
                        summary[op]['time_avg'] = self.compute_seconds_uperf(avg)
                        summary[op]['time_max'] = self.compute_seconds_uperf(maximum)
                        summary[op]['time_min'] = self.compute_seconds_uperf(minimum)
                    elif line.startswith('** Error') or (line.startswith('WARNING: Errors') and not failed):
                        failure_message = line
                        failed = True
                        self.timestamp(f"Test case {test_name} failed!")
                        failed_cases.append(test_name)
                    elif line.startswith('*'):
                        self.timestamp(line)
                    else:
                        pass
                    line = run.stdout.readline().decode('ascii')
                status = run.poll()
                if failed or status != 0:
                    self.timestamp(f"Uperf failed: {status}")
                    return 1
            job_end_time = self.adjusted_time()
            data_end_time = job_end_time
            summary['raw_elapsed_time'] = last_time - first_time
            summary['raw_nbytes'] = last_nbytes
            summary['raw_nops'] = last_nops
            if summary['raw_elapsed_time'] > 0:
                summary['raw_avg_ops_sec'] = summary['raw_nops'] / summary['raw_elapsed_time']
                summary['raw_avg_bytes_sec'] = summary['raw_nbytes'] / summary['raw_elapsed_time']
            summary['nbytes'] = 0
            summary['nops'] = 0
            summary['elapsed_time'] = 0
            summary['avg_bytes_sec'] = 0
            summary['avg_ops_sec'] = 0
            ops_sec_sum = 0
            ops_sec_sq_sum = 0
            bytes_sec_sum = 0
            bytes_sec_sq_sum = 0
            stdev_counter = 0
            for point in timeseries:
                if summary['raw_elapsed_time'] < 10 or (point['time'] >= self.ramp_time and
                                                        point['time'] < summary['raw_elapsed_time'] - self.ramp_time):
                    summary['nbytes'] += point['nbytes']
                    summary['nops'] += point['nops']
                    summary['elapsed_time'] += point['timedelta']
                    ops_sec = point['nops'] / point['timedelta']
                    bytes_sec = point['nbytes'] / point['timedelta']
                    ops_sec_sum += ops_sec
                    ops_sec_sq_sum += ops_sec ** 2
                    bytes_sec_sum += bytes_sec
                    bytes_sec_sq_sum += bytes_sec ** 2
                    stdev_counter += 1
            if summary['elapsed_time'] > 0:
                summary['avg_bytes_sec'] = summary['nbytes'] / summary['elapsed_time']
                summary['avg_ops_sec'] = summary['nops'] / summary['elapsed_time']
                summary['bytes_sec_sq_sum'] = bytes_sec_sq_sum
                summary['bytes_sec_sum'] = bytes_sec_sum
                summary['ops_sec_sq_sum'] = ops_sec_sq_sum
                summary['ops_sec_sum'] = ops_sec_sum
                if stdev_counter >= 2:
                    summary['stdev_bytes_sec'] = ((bytes_sec_sq_sum / stdev_counter) - (summary['avg_bytes_sec'] ** 2)) ** 0.5
                    summary['stdev_ops_sec'] = ((ops_sec_sq_sum / stdev_counter) - (summary['avg_ops_sec'] ** 2)) ** 0.5
                else:
                    summary['stdev_bytes_sec'] = 0
                    summary['stdev_ops_sec'] = 0
            summary['job_start_time'] = job_start_time
            summary['job_end_time'] = job_end_time
            case = {
                'metadata': metadata,
                'summary': summary,
                'timeseries': timeseries,
                'status': {
                    'message': failure_message
                    }
                }
            if failed:
                case['status']['condition'] = 'FAIL'
            else:
                case['status']['condition'] = 'PASS'
            elapsed_time += summary['elapsed_time']
            counter = counter + 1
            cases[test_name] = case
        results['results'] = cases
        results['failed'] = failed_cases
        ucpu, scpu = self.cputimes(ucpu, scpu)
        self.report_results(data_start_time, data_end_time, elapsed_time, ucpu, scpu, results)


uperf_client().run_workload()
