#!/usr/bin/env python3

# Copyright 2022 Robert Krawitz/Red Hat
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import time
from datetime import datetime
import socket
import re
import json
import os
import sys
import subprocess
import signal
import math
import random
from resource import getrusage, RUSAGE_SELF, RUSAGE_CHILDREN


class clusterbuster_pod_client:
    def __init__(self, argv: list = sys.argv):
        if len(argv) < 9:
            print("clusterbuster_pod_client: incomplete argument list", file=sys.stderr)
            os._exit(1)
        print(f"clusterbuster_pod_client {argv}", file=sys.stderr)
        self.__namespace = argv[1]
        self.__container = argv[2]
        self.__basetime = float(argv[3])
        self.__baseoffset = float(argv[4])
        self.__crtime = float(argv[5])
        self.__exit_at_end = bool(argv[6])
        self.__synchost = argv[7]
        self.__syncport = int(argv[8])
        self.__start_time = float(time.time())
        self.__pod = socket.gethostname()
        self.__extra_args = argv[9:]
        self.__timing_parameters = {}
        self.__timing_initialized = False
        self.__child_idx = None

    def toBool(arg, defval: bool = None):
        if isinstance(arg, bool):
            return arg
        if isinstance(arg, (int, float)):
            return arg != 0
        if isinstance(arg, str):
            arg = arg.lower()
            if arg == 'true' or arg == 'yes':
                return True
            elif arg == 'false' or arg == 'no':
                return False
            try:
                arg1 = int(arg)
                return arg1 != 0
            except Exception:
                pass
        if defval is not None:
            return defval
        raise Exception(f'Cannot parse {arg} as a boolean value')

    def verbose(self):
        return clusterbuster_pod_client.toBool(os.environ.get('VERBOSE', 0))

    def _run_cmd(self, cmd):
        try:
            answer = subprocess.run(cmd, stdout=subprocess.PIPE)
            return self.get_timestamp(f'{cmd} output:\n{answer.stdout.decode("ascii")}')
        except Exception as err:
            return self.get_timestamp(f"Can't run {cmd}: {err}")

    def _clean_numbers(self, ref):
        # Perl to_json encodes innfinity as inf and NaN as nan.
        # This results in invalid JSON.  It's our responsibility to sanitize
        # this up front.
        # https://docs.python.org/3.8/library/json.html#infinite-and-nan-number-values
        if isinstance(ref, dict):
            answer = dict()
            for key, val in ref.items():
                answer[key] = self._clean_numbers(val)
            return answer
        elif isinstance(ref, list):
            return [self._clean_numbers[item] for item in ref]
        elif isinstance(ref, float) and (math.isnan(ref) or math.isinf(ref)):
            return None
        else:
            return ref

    def _ts(self):
        return datetime.utcfromtimestamp(time.time() - self.__timing_parameters.get('local_offset_from_sync', 0)).strftime('%Y-%m-%dT%T.%f')

    def calibrate_time(self):
        time_overhead = 0
        for i in range(1000):
            start = self.adjusted_time()
            end = self.adjusted_time()
            time_overhead += end - start
        return time_overhead / 1000

    def cputimes(self):
        r_self = getrusage(RUSAGE_SELF)
        r_children = getrusage(RUSAGE_CHILDREN)
        return (r_self.ru_utime + r_children.ru_utime, r_self.ru_stime + r_children.ru_stime)

    def cputime(self):
        r_self = getrusage(RUSAGE_SELF)
        r_children = getrusage(RUSAGE_CHILDREN)
        return r_self.ru_utime + r_children.ru_utime + r_self.ru_stime + r_children.ru_stime

    def adjusted_time(self):
        if 'xtime_adjustment' in self.__timing_parameters:
            return time.time() - self.__timing_parameters['xtime_adjustment']
        else:
            return time.time()

    def get_timestamp(self, string: str):
        string = re.sub(r'\n(.*\S.*)', r'\n            \1', string)
        return '%7d %s %s\n' % (os.getpid(), self._ts(), string)

    def timestamp(self, string):
        print(self.get_timestamp(str(string)), file=sys.stderr, end='')

    def drop_cache(self, service: str, port: int):
        self.timestamp("Dropping local cache")
        subprocess.run('sync')
        self.timestamp("Dropping host cache")
        with self.connect_to(service, port) as sock:
            self.timestamp(f"    Connected to {service}:{port}")
            sock.recv(1)
            self.timestamp("    Confirmed")

    def podname(self):
        return self.__pod

    def container(self):
        return self.__container

    def namespace(self):
        return self.__namespace

    def idname(self, extra_components: list = None):
        sep = ':'
        if extra_components is not None and len(extra_components) > 0 and extra_components[0] == '-d':
            sep = '-'
            extra_components = extra_components[1:]
        components = [self.namespace(), self.podname(), self.container(), str(os.getpid())]
        if extra_components is not None:
            components = components + [str(c) for c in extra_components]
        return sep.join(components)

    def command_line(self):
        return self.__extra_args

    def _fsplit(self, string: str):
        return [float(s) for s in string.split()]

    def initialize_timing(self, name_components: list = None):
        if self.__timing_initialized:
            return
        name = self.idname(name_components)
        self.timestamp("About to sync")
        data = self._do_sync_command('TIME', f'timestamp: %s {name}')
        try:
            local_sync_start, remote_sync_start, absolute_sync_start, remote_sync_base, remote_sync, sync_base_start_time = self._fsplit(data.decode('ascii'))
        except Exception as err:
            self.timestamp(f"Could not parse response from server: {data}: {err}")
            os._exit(1)
        local_sync = float(time.time())
        local_sync_rtt = local_sync - local_sync_start
        remote_sync_rtt = remote_sync - remote_sync_start
        local_offset_from_sync = (local_sync - remote_sync) - ((local_sync_rtt - remote_sync_rtt) / 2)
        adjusted_start_time = self.__start_time - local_offset_from_sync
        start_offset_from_base = adjusted_start_time - self.__basetime
        local_offset_from_base = local_offset_from_sync + start_offset_from_base
        sync_rtt_delta = local_sync_rtt - remote_sync_rtt
        xtime_adjustment = self.__basetime + local_offset_from_sync

        self.__timing_parameters = {
            'sync_pod_start': absolute_sync_start,
            'controller_basetime': self.__basetime,
            'controller_crtime': self.__crtime,
            'local_offset_from_sync': local_offset_from_sync,
            'local_start_time': adjusted_start_time,
            'local_sync': local_sync,
            'local_sync_rtt': local_sync_rtt,
            'local_sync_start': local_sync_start,
            'local_sync_time': local_sync,
            'remote_sync': remote_sync,
            'remote_sync_base': remote_sync_base,
            'remote_sync_offset': remote_sync - remote_sync_base,
            'remote_sync_rtt': remote_sync_rtt,
            'remote_sync_start': remote_sync_start,
            'start_time': start_offset_from_base,
            'sync_rtt_delta': sync_rtt_delta,
            'xtime_adjustment': xtime_adjustment,
            'remote_sync_base_start_time': sync_base_start_time,
            'local_base_start_time': self.__start_time,
            'local_offset_from_sync': local_offset_from_sync,
            'local_offset_from_base': local_offset_from_base,
            }
        self.timestamp("Timing parameters:")
        for key, val in self.__timing_parameters.items():
            self.timestamp('%-32s %.6f' % (key, val))
            self.__basetime += self.__baseoffset
            self.__crtime += self.__baseoffset
        self.__timing_initialized = True

    def connect_to(self, addr: str = None, port: int = None):
        if addr is None:
            addr = self.__synchost
        if port is None:
            port = self.__syncport
        while True:
            try:
                try:
                    sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
                except Exception as err:
                    self.timestamp(f"Cannot create socket: {err}")
                    os._exit(1)
                # We call gethostbyname() each time through the loop because
                # the remote hostname might not exist immediately.
                sock.connect((addr, port))
                return sock
            except Exception as err:
                self.timestamp(f"Cannot connect to {addr} on port {port}: {err}")
                time.sleep(1)
            sock.close()

    def listen(self, addr: str = None, port: int = None, backlog=5):
        if addr is None:
            addr = ''
        try:
            sock = socket.socket()
            sock.bind(('', port))
            sock.listen(backlog)
            return sock
        except Exception as err:
            self.timestamp(f"Cannot create listener: {err}")
            os._exit(1)

    def _do_sync_command(self, command: str, token: str = ''):
        lcommand = command.lower()
        if lcommand == 'sync' and (token is None or token == ''):
            token = f'{self._ts()} {self.__pod()}-{random.randrange(1000000000)}'
        token = f'{command} {token}'.replace('%s', str(time.time()))
        token = ('0x%08x%s' % (len(token), token)).encode()
        while True:
            self.timestamp(f'sync on {self.__synchost}:{self.__syncport}')
            sync_conn = self.connect_to()
            while len(token) > 0:
                if len(token) > 128:
                    self.timestamp(f'Writing {command}, {len(token)} bytes to sync')
                else:
                    self.timestamp(f'Writing token {token} to sync')
                try:
                    answer = sync_conn.send(token)
                    if answer <= 0:
                        self.timestamp("Write token failed")
                    else:
                        token = token[answer:]
                except Exception as err:
                    self.timestamp(f'Write token failed: {err}')
                    os._exit(1)
            try:
                answer = sync_conn.recv(1024)
                sync_conn.close()
                self.timestamp(f'sync complete, response {answer}')
                return answer
            except Exception as err:
                self.timestamp(f'sync failed {err}, retrying')

    def _finish(self, status=0, pid=os.getpid()):
        answer = f'{self._run_cmd("lscpu")}{self._run_cmd("dmesg")}'
        print(answer, file=sys.stderr)
        if status != 0:
            print("FAIL!", file=sys.stderr)
            buf = f'''
Namespace/pod/container: {self.namespace()}/{self.podname()}/{self.container()} pid: {pid}
{answer}
Run:
oc logs -n '{self.namespace()}' '{self.podname()}' -c '{self.container()}'
'''
            self._do_sync_command('FAIL', buf)
            if self.__exit_at_end:
                os._exit(status)
        pid_status = 0
        if self.__exit_at_end:
            self.timestamp('About to exit')
            try:
                while True:
                    pid, status = os.wait()
                    if status != 0:
                        status = int((status / 256)) | (status & 255)
                        self.timestamp(f'Pid {pid} returned status {status}')
                        pid_status = status
            except ChildProcessError:
                pass
            except Exception as err:
                self.timestamp(f"wait() failed: {err}")
            self.timestamp('Done waiting')
            print('FINIS', file=sys.stderr)
            os._exit(pid_status)
        else:
            self.timestamp('Waiting forever')
            signal.pause()

    def run_workload(self, run_func, processes: int = 1, initialize_timing_if_needed: bool = True, *args):
        if processes < 1:
            processes = 1
        pid_count = 0
        for i in range(processes):
            try:
                try:
                    child = os.fork()
                except Exception as err:
                    self.timestamp(f"Fork failed: {err}")
                    os._exit(1)
                if child == 0:  # Child
                    self.__child_idx = i
                    if initialize_timing_if_needed and not self.__timing_initialized:
                        self.initialize_timing()
                    self.timestamp(f"About to run subprocess {i}")
                    status = run_func(self, i, *args)
                    self.timestamp(f"{os.getpid()} exiting, status {status}")
                    os._exit(status)
                else:
                    pid_count = pid_count + 1
            except Exception as err:
                self.timestamp(f"Subprocess {i} failed: {err}")
                os._exit(1)
        while pid_count > 0:
            try:
                pid, status = os.wait()
                status = int((status / 256)) | (status & 255)
                self.timestamp(f"waited for {pid} => {status}")
                if status != 0:
                    self._finish(status, pid)
                pid_count = pid_count - 1
            except Exception as err:
                self.timestamp(f'Wait failed: {err}')
                self._finish(1)
        self._finish()

    def report_results(self, data_start_time: float, data_end_time: float,
                       data_elapsed_time: float, user_cpu: float, sys_cpu: float, extra: dict = None):
        answer = {
            'application': 'clusterbuster-json',
            'namespace': self.namespace(),
            'pod': self.podname(),
            'container': self.container(),
            'process_id': os.getpid(),
            'pod_create_time': self.__timing_parameters['controller_crtime'] - self.__timing_parameters['controller_basetime'],
            'pod_start_time': self.__timing_parameters['start_time'],
            'data_start_time': data_start_time,
            'data_end_time': data_end_time,
            'data_elapsed_time': data_elapsed_time,
            'user_cpu_time': user_cpu,
            'system_cpu_time': sys_cpu,
            'cpu_time': user_cpu + sys_cpu,
            'timing_parameters': self.__timing_parameters
            }
        if isinstance(extra, dict):
            for key, val in extra.items():
                answer[key] = val
        self.timestamp(f"Report results: {self.namespace()}, {self.podname()}, {self.container()}, {os.getpid()}")
        self._do_sync_command('RSLT', json.dumps(self._clean_numbers(answer)))

    def sync_to_controller(self, token: str = None):
        self._do_sync_command('SYNC', token)
