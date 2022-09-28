#!/usr/bin/env python3

import os
import subprocess
import re
import shutil

from clusterbuster_pod_client import clusterbuster_pod_client


class sysbench_client(clusterbuster_pod_client):
    """
    sysbench test for clusterbuster
    """

    def __init__(self):
        super().__init__()
        self.processes = int(self._args[0])
        self.rundir = self._args[1]
        self.runtime = int(self._args[2])
        self.sysbench_generic_args = clusterbuster_pod_client.splitStr(r'\s+', self._args[3])
        self.sysbench_cmd = self._args[4]
        self.sysbench_fileio_args = clusterbuster_pod_client.splitStr(r'\s+', self._args[5])
        if self._args[6]:
            self.sysbench_modes = clusterbuster_pod_client.splitStr(r'\s+', self._args[6])
        else:
            self.sysbench_modes = ['seqwr', 'seqrewr', 'seqrd', 'rndrd', 'rndwr', 'rndrw']

    def build_sysbench_cmd(self, command: str, mode: str):
        args = ['sysbench', f'--time={self.runtime}']
        args.extend(self.sysbench_generic_args)
        args.extend([self.sysbench_cmd, command, f'--file-test-mode={mode}'])
        args.extend(self.sysbench_fileio_args)
        return args

    def simple_check1(self, m, op_answer: dict, key: str, multiplier: float, matchidx: int, is_float: bool, is_str: bool, is_int: bool):
        if is_str:
            op_answer[key] = m.group(matchidx)
        elif is_float:
            op_answer[key] = float(m.group(matchidx)) * multiplier
        else:
            op_answer[key] = self.toSize(m.group(matchidx)) * multiplier

    def simple_check(self, pattern: str, line: str, op_answer: dict, key, multiplier = None, matchidx = None, is_float: bool=False, is_str: bool=False, is_int: bool=True):
        m = re.match(pattern, line)
        if not m:
            return False
        if isinstance(key, list):
            if multiplier is None:
                multiplier = [1.0 for i in range(len(key))]
            elif isinstance(multiplier, int) or isinstance(multiplier, float):
                multiplier = [multiplier for i in range(len(key))]
            elif not isinstance(matchidx, list) or len(matchidx) < len(key):
                raise Exception("Non-conformant multiplier")
            if not isinstance(matchidx, list) or len(matchidx) < len(key):
                raise Exception("Non-conformant multiplier")
            for i in range(len(key)):
                self.simple_check1(m, op_answer, key[i], multiplier[i], matchidx[i], is_float, is_str, is_int)
        else:
            if matchidx is None:
                matchidx = 1
            if multiplier is None:
                multiplier = 1
            self.simple_check1(m, op_answer, key, multiplier, matchidx, is_float, is_str, is_int)
        return True

    def runit(self, process: int):
        op_answers = {}
        localrundir = f'{self.rundir}/{self.podname()}/{str(os.getpid)}'
        shutil.rmtree(localrundir, ignore_errors=True)
        os.makedirs(localrundir)
        os.chdir(localrundir)
        data_start_time = self.adjusted_time()
        user, sys = self.cputimes()
        for mode in self.sysbench_modes:
            self.sync_to_controller(f'{mode}+prepare')
            self.timestamp("Preparing...")
            args = self.build_sysbench_cmd('prepare', mode)
            self.timestamp(" ".join(args))
            subprocess.run(args, check=True)

            self.sync_to_controller(f'{mode}+run')
            op_user, op_sys = self.cputimes()
            self.timestamp("Running...")
            args = self.build_sysbench_cmd('run', mode)
            self.timestamp(" ".join(args))
            np = '([0-9]+([kmgt]i)?)b'
            with subprocess.Popen(args, stdout=subprocess.PIPE) as run:
                op_answer = {
                    'final_fsync_enabled': 'Disabled',
                    'io_mode': 'unknown',
                    'rdwr_ratio': 1
                    }
                line = run.stdout.readline().decode('ascii')
                while line:
                    line = line.strip().lower()
                    self.timestamp(line)
                    if self.simple_check(rf'([0-9]+) *files, *{np}', line, op_answer, ['files', 'filesize'], matchidx=[1, 2]):
                        pass
                    elif self.simple_check(rf'block size *{np}', line, op_answer, 'blocksize'):
                        pass
                    elif self.simple_check(r'read/write ratio for combined random io test: *([0-9]+(\.[0-9]+)?)', line, op_answer, 'rdwr_ratio', is_float=True):
                        pass
                    elif self.simple_check(r'periodic fsync enabled, calling fsync.. each ([0-9]+)', line, op_answer, 'fsync_frequency'):
                        pass
                    elif self.simple_check(r'calling fsync.. at the end of test, (enabled|disabled)', line, op_answer, 'final_fsync_enabled', is_str=True):
                        pass
                    elif self.simple_check(r'using (.*) i/o mode', line, op_answer, 'io_mode', is_str = True):
                        pass
                    elif self.simple_check(r'reads/s: *([0-9.]+)', line, op_answer, 'read_ops'):
                        pass
                    elif self.simple_check(r'writes/s: *([0-9.]+)', line, op_answer, 'write_ops'):
                        pass
                    elif self.simple_check(r'fsyncs/s: *([0-9.]+)', line, op_answer, 'fsync_ops'):
                        pass
                    elif self.simple_check(r'read, mib/s: *([0-9.]+)', line, op_answer, 'read_rate_mb_sec'):
                        pass
                    elif self.simple_check(r'written, mib/s: *([0-9.]+)', line, op_answer, 'write_rate_mb_sec'):
                        pass
                    elif self.simple_check(r'total time: *([0-9.]+)s', line, op_answer, 'elapsed_time'):
                        pass
                    elif self.simple_check(r'min: *([0-9.]+)', line, op_answer, 'min_latency_sec'):
                        pass
                    elif self.simple_check(r'avg: *([0-9.]+)', line, op_answer, 'avg_latency_sec'):
                        pass
                    elif self.simple_check(r'max: *([0-9.]+)', line, op_answer, 'max_latency_sec'):
                        pass
                    elif self.simple_check(r'95th percentile: *([0-9.]+)', line, op_answer, 'p95_latency_sec'):
                        pass
                    line = run.stdout.readline().decode('ascii')
                status = run.poll()
                if status:
                    self.timestamp(f"Sysbench failed: {status}")
                    return 1
            op_answer['user_cpu_time'], op_answer['sys_cpu_time'] = self.cputimes(op_user, op_sys)
            self.sync_to_controller(f'{mode}+finish')
            self.timestamp("Preparing...")
            args = self.build_sysbench_cmd('cleanup', mode)
            self.timestamp(" ".join(args))
            subprocess.run(args, check=True)
            op_answers[mode] = op_answer
        data_end_time = self.adjusted_time()
        elapsed_time = data_end_time - data_start_time
        user, sys = self.cputimes(user, sys)
        extras = {
            'workloads': op_answers
            }
        self.report_results(data_start_time, data_end_time, elapsed_time, user, sys, extras)


sysbench_client().run_workload()
