#!/usr/bin/env python3

import os
import subprocess
import re
import shutil
import time

from clusterbuster_pod_client import clusterbuster_pod_client


class sysbench_client(clusterbuster_pod_client):
    """
    sysbench test for clusterbuster
    """

    def __init__(self):
        try:
            super().__init__()
            self.np = '([0-9]+([kmgt]i)?)b'
            self._set_processes(int(self._args[0]))
            self.rundir = self._args[1]
            self.runtime = int(self._args[2])
            self.workload = self._args[3]
            if self._args[4]:
                self.sysbench_fileio_tests = self._splitStr(r'\s+', self._args[4])
            else:
                self.sysbench_fileio_tests = ['seqwr', 'seqrewr', 'seqrd', 'rndrd', 'rndwr', 'rndrw']
            if self._args[5]:
                self.sysbench_fileio_modes = self._splitStr(r'\s+', self._args[5])
            else:
                self.sysbench_fileio_modes = ['sync']
            self.sysbench_options = self._args[6:]
            self.runit_cpu = self.runit_simple
            self.runit_memory = self.runit_simple
            self.runit_mutex = self.runit_simple
            self.runit_threads = self.runit_simple
        except Exception as err:
            self._abort(f"Init failed! {err} {' '.join(self._args)}")

    def build_sysbench_cmd(self, command: str, *argv):
        args = ['sysbench', f'--time={self.runtime}', self.workload, command]
        args.extend(argv)
        args.extend(self.sysbench_options)
        return args

    def simple_check1(self, m, op_answer: dict, key: str, multiplier: float, matchidx: int,
                      is_float: bool, is_str: bool, is_int: bool):
        if is_str:
            op_answer[key] = m.group(matchidx)
        elif is_float:
            op_answer[key] = float(m.group(matchidx)) * multiplier
        else:
            op_answer[key] = self._toSize(m.group(matchidx)) * multiplier

    def simple_check(self, pattern: str, line: str, op_answer: dict, key, multiplier=None, matchidx=None,
                     is_float: bool = False, is_str: bool = False, is_int: bool = True):
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

    def runit_simple(self, process: int):
        args = self.build_sysbench_cmd('run')
        self._sync_to_controller()
        self._timestamp(f'Running {" ".join(args)}')
        data_start_time = self._adjusted_time()
        user, sys = self._cputimes()
        op_answer = {
            'op_start': self._adjusted_time(),
            'workload': self.workload
            }
        with subprocess.Popen(args, stdout=subprocess.PIPE) as run:
            line = run.stdout.readline().decode('ascii')
            while line:
                line = line.strip().lower()
                self._timestamp(line)
                if self.simple_check(r'number of threads: *([0-9]+)', line, op_answer, 'threads'):
                    pass
                elif self.simple_check(r'events per second: *([0-9.]+)', line, op_answer, 'events_per_second', is_float=True):
                    pass
                elif self.simple_check(r'total time: *([0-9.]+)s', line, op_answer, 'elapsed_time', is_float=True):
                    pass
                elif self.simple_check(r'total number of events: *([0-9]+)', line, op_answer, 'total_events'):
                    pass
                elif self.simple_check(r'min: *([0-9.]+)', line, op_answer, 'min_latency_sec', is_float=True):
                    pass
                elif self.simple_check(r'avg: *([0-9.]+)', line, op_answer, 'avg_latency_sec', is_float=True):
                    pass
                elif self.simple_check(r'max: *([0-9.]+)', line, op_answer, 'max_latency_sec', is_float=True):
                    pass
                elif self.simple_check(r'95th percentile: *([0-9.]+)', line, op_answer, 'p95_latency_sec', is_float=True):
                    pass
                elif self.simple_check(r'events .avg/stddev.:\s*([0-9.]+)/([0-9.]+)', line,
                                       op_answer, ['events_avg', 'events_stdev'],
                                       matchidx=[1, 2], is_float=True):
                    pass
                elif self.simple_check(r'execution time .avg/stddev.:\s*([0-9.]+)/([0-9.]+)', line,
                                       op_answer, ['time', 'time_stdev'],
                                       matchidx=[1, 2], is_float=True):
                    pass
                line = run.stdout.readline().decode('ascii')
            status = run.wait()
            if status:
                raise Exception(f"Sysbench failed: {status}")
        op_answer['op_end'] = self._adjusted_time()
        data_end_time = self._adjusted_time()
        elapsed_time = data_end_time - data_start_time
        user, sys = self._cputimes(user, sys)
        op_answer['user_cpu_time'] = user
        op_answer['sys_cpu_time'] = sys
        extras = {
            'workloads': {self.workload: op_answer}
            }
        self._report_results(data_start_time, data_end_time, elapsed_time, user, sys, extras)

    def runit_fileio(self, process: int):
        op_answers = {}
        localrundir = f'{self.rundir}/{self._podname()}/{str(os.getpid())}'
        shutil.rmtree(localrundir, ignore_errors=True)
        while True:
            try:
                os.makedirs(localrundir)
                break
            except Exception as exc:
                self._timestamp(f"makedirs failed {exc}; retrying")
                time.sleep(1)
        os.chdir(localrundir)
        data_start_time = self._adjusted_time()
        user, sys = self._cputimes()
        for mode in self.sysbench_fileio_modes:
            for test in self.sysbench_fileio_tests:
                self._sync_to_controller(f'{test}+{mode}+prepare')
                args = self.build_sysbench_cmd('prepare', f'--file-test-mode={test}', f'--file-io-mode={mode}')
                self._timestamp(f'Preparing {" ".join(args)}')
                subprocess.run(args, check=True)

                self._drop_cache()
                self._sync_to_controller(f'{test}+{mode}+run')
                op_user, op_sys = self._cputimes()
                args = self.build_sysbench_cmd('run', f'--file-test-mode={test}', f'--file-io-mode={mode}')
                self._timestamp(f'Running {" ".join(args)}')
                op_answer = {
                    'final_fsync_enabled': 'Disabled',
                    'io_mode': 'unknown',
                    'workload': test,
                    'rdwr_ratio': 1,
                    'op_start': self._adjusted_time()
                    }
                with subprocess.Popen(args, stdout=subprocess.PIPE) as run:
                    line = run.stdout.readline().decode('ascii')
                    while line:
                        line = line.strip().lower()
                        self._timestamp(line)
                        if self.simple_check(rf'([0-9]+) *files, *{self.np}', line,
                                             op_answer, ['files', 'filesize'], matchidx=[1, 2]):
                            pass
                        elif self.simple_check(rf'block size *{self.np}', line, op_answer, 'blocksize'):
                            pass
                        elif self.simple_check(r'read/write ratio for combined random io test: *([0-9]+(\.[0-9]+)?)',
                                               line, op_answer, 'rdwr_ratio', is_float=True):
                            pass
                        elif self.simple_check(r'periodic fsync enabled, calling fsync.. each ([0-9]+)',
                                               line, op_answer, 'fsync_frequency'):
                            pass
                        elif self.simple_check(r'calling fsync.. at the end of test, (enabled|disabled)',
                                               line, op_answer, 'final_fsync_enabled', is_str=True):
                            pass
                        elif self.simple_check(r'using (.*) i/o mode', line, op_answer, 'io_mode', is_str=True):
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
                    status = run.wait()
                    if status:
                        raise Exception(f"Sysbench failed: {status}")
                op_answer['op_end'] = self._adjusted_time()
                op_answer['user_cpu_time'], op_answer['sys_cpu_time'] = self._cputimes(op_user, op_sys)
                self._sync_to_controller(f'{test}+{mode}+finish')
                args = self.build_sysbench_cmd('cleanup', f'--file-test-mode={test}', f'--file-io-mode={mode}')
                self._timestamp(f'Cleanup {" ".join(args)}')
                subprocess.run(args, check=True)
                op_answers[f'fileio+{test}+{mode}'] = op_answer
        data_end_time = self._adjusted_time()
        elapsed_time = data_end_time - data_start_time
        user, sys = self._cputimes(user, sys)
        extras = {
            'workloads': op_answers
            }
        self._report_results(data_start_time, data_end_time, elapsed_time, user, sys, extras)

    def runit(self, process: int):
        func = getattr(self, f'runit_{self.workload}', None)
        if func:
            func(process)
        else:
            self.runit_simple(process)


sysbench_client().run_workload()
