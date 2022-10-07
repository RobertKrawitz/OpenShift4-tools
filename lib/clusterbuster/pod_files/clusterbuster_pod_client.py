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
import socket
import json
import os
import sys
import subprocess
import signal
import random
import traceback
from cb_util import cb_util


class clusterbuster_pod_client(cb_util):
    """
    Python interface to the ClusterBuster pod API
    """

    def __init__(self, initialize_timing_if_needed: bool = True, argv: list = sys.argv):
        super().__init__()
        print(f'Args: {" ".join(argv)}', file=sys.stderr)
        # No use in catching errors here, since we may not be sufficiently initialized
        # to signal them back.
        if len(argv) < 9:
            print("clusterbuster_pod_client: incomplete argument list", file=sys.stderr)
            os._exit(1)
        print(f"clusterbuster_pod_client {argv}", file=sys.stderr)
        self.__namespace = argv[1]
        self.__container = argv[2]
        self.__basetime = float(argv[3])
        self.__baseoffset = float(argv[4])
        self.__crtime = float(argv[5])
        self.__exit_at_end = self._toBool(argv[6])
        self.__synchost = argv[7]
        self.__syncport = int(argv[8])
        self.__is_worker = False
        self.__start_time = float(time.time())
        self.__enable_sync = True
        try:
            child = os.fork()
        except Exception as err:
            print(f"Fork failed: {err}", file=sys.stderr)
            if self.__exit_at_end:
                os._exit(1)
            else:
                while True:
                    signal.pause()
        if child == 0:
            self.__pod = socket.gethostname()
            self._args = argv[9:]
            self.__timing_parameters = {}
            self.__timing_initialized = False
            if initialize_timing_if_needed:
                self.__initialize_timing()
            self._set_offset(self.__timing_parameters.get('local_offset_from_sync', 0))
            self.__child_idx = None
            self.__processes = 1
            self._set_preferred_ip_addr(self._get_primary_ip())
        else:
            try:
                pid, status = os.wait()
                status = int((status / 256)) | (status & 255)
                if status:
                    print(f"Child process {pid} failed: {status}")
                else:
                    print("Child process {pid} succeeded")
                if self.__exit_at_end:
                    os._exit(status)
                else:
                    while True:
                        signal.pause()
            except Exception as err:
                self._abort(f"Wait failed: {err}")

    def run_workload(self):
        """
        Run a workload.  This method does not return.  The workload
        is expected to take a process number.  This is the only public
        method.
        """
        if self.__processes < 1:
            self.__processes = 1
        pid_count = 0
        for i in range(self.__processes):
            try:
                try:
                    child = os.fork()
                except Exception as err:
                    self._timestamp(f"Fork failed: {err}")
                    os._exit(1)
                if child == 0:  # Child
                    self.__is_worker = True
                    self.__child_idx = i
                    self._timestamp(f"About to run subprocess {i}")
                    try:
                        self.runit(i)
                        self._timestamp(f"{os.getpid()} complete")
                        self.__finish()
                    except Exception as err:
                        # If something goes wrong with the workload that isn't caught,
                        # a traceback will likely be useful
                        self.__finish(False, message=f'{err}\n{traceback.format_exc()}')
                    raise Exception("runWorkload should not reach this point!")
                else:
                    pid_count = pid_count + 1
            except Exception as err:
                self.__finish(False, message=f"Subprocess {i} failed: {err}")
        messages = []
        while pid_count > 0:
            try:
                pid, status = os.wait()
                if status & 255:
                    messages.append(f"Process {pid} killed by signal {status & 255}")
                elif status / 256:
                    messages.append(f"Process {pid} failed with status {int(status / 256)}")
                else:
                    self._timestamp(f"Process {pid} completed normally")
                pid_count = pid_count - 1
            except Exception as err:
                self.__finish(False, message=f'Wait failed: {err}')
        self._timestamp(f'{self._run_cmd("lscpu")}\n{self._run_cmd("dmesg")}')
        if messages:
            self.__finish(False, message='\n'.join(messages))
        else:
            self.__finish()

    def _verbose(self):
        """
        Should we be verbose?
        :return: whether we should print verbose messages
        """
        return self._toBool(os.environ.get('VERBOSE', 0))

    def _set_processes(self, processes: int = 1):
        """
        Set the number of processes to be run
        """
        self.__processes = processes

    def _calibrate_time(self):
        """
        Estimate the time required to retrieve the system time
        :return: Estimated time overhead in seconds for self._adjusted_time
        """
        time_overhead = 0
        for i in range(1000):
            start = self._adjusted_time()
            end = self._adjusted_time()
            time_overhead += end - start
        return time_overhead / 1000

    def _adjusted_time(self, otime: float = 0):
        """
        Return system time normalized to the host time
        :return: System time, normalized to the host time
        """
        if 'xtime_adjustment' in self.__timing_parameters:
            return time.time() - self.__timing_parameters['xtime_adjustment'] - otime
        else:
            return time.time() - otime

    def _drop_cache(self, service: str = None, port: int = None):
        """
        Attempt to drop buffer cache locally and on remote (typically hypervisor)
        :param service: Service for requesting drop cache
        :param port: Port for requesting drop cache
        """
        self._timestamp("Dropping local cache")
        subprocess.run('sync')
        self._timestamp("Dropping host cache")
        if service and port:
            with self._connect_to(service, port) as sock:
                self._timestamp(f"    Connected to {service}:{port}")
                sock.recv(1)
                self._timestamp("    Confirmed")

    def _podname(self):
        """
        :return: name of our pod
        """
        return self.__pod

    def _container(self):
        """
        :return: name of the container we're running in
        """
        return self.__container

    def _namespace(self):
        """
        :return: namespace that we're running in
        """
        return self.__namespace

    def _idname(self, args: list = None, separator: str = ':'):
        """
        Generate an identifier based on namespace, pod, container, process ID, and any other desired values
        :param separator: Separator to be used between components (default ':')
        :param extra_components: Any extra components to be appended to the id
        :return: Identification string
        """
        components = [self._namespace(), self._podname(), self._container(), str(os.getpid())]
        if args is not None:
            components = components + [str(c) for c in args]
        return separator.join(components)

    def _report_results(self, data_start_time: float, data_end_time: float,
                        data_elapsed_time: float, user_cpu: float, sys_cpu: float, extra: dict = None):
        """
        Report results back to the controller
        :param data_start_time: Adjusted time work started
        :param data_end_time: Adjusted time work ended
        :param data_elapsed_time: Time that workload was running (may be less than data_end_time - data_start_time)
        :param user_cpu: User CPU consumed by the workload
        :param sys_cpu: System CPU consumed by the workload
        :param extra: Optional dict containing additional results
        """
        if not self.__is_worker:
            raise Exception("_report_results must not be called outside of a worker")
        answer = {
            'application': 'clusterbuster-json',
            'namespace': self._namespace(),
            'pod': self._podname(),
            'container': self._container(),
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
        self._timestamp(f"Report results: {self._namespace()}, {self._podname()}, {self._container()}, {os.getpid()}")
        try:
            answer = json.dumps(self._clean_numbers(answer))
        except Exception as exc:
            self.__fail(f"Cannot convert results to JSON: {exc}")
        self.__do_sync_command('RSLT', answer)

    def _enable_sync(self, enable_sync: bool = True):
        """
        Enable sync to controller.  Normally true unless you are running
        a workload that should not attempt to sync
        """
        self.__enable_sync = enable_sync

    def _sync_to_controller(self, token: str = None):
        """
        Perform a sync to the controller
        :param token: Optional string to use for sync; None to generate one
        """
        if self.__enable_sync:
            self._timestamp(f"do_sync_command {token}")
            self.__do_sync_command('SYNC', token)

    def _abort(self, msg: str = "Terminating"):
        """
        Abort the run.  This is intended to be called from inside the workload's
        constructor if something goes wrong in initialization and should not be used
        otherwise.
        :param msg: Message to be logged
        """
        try:
            message = f"Process {os.getpid()} aborting: {msg}\n{traceback.format_exc()}"
        except Exception:
            message = f"Process {os.getpid()} aborting: {msg} (no traceback)"
        self.__finish(False, message=message)

    def _set_preferred_ip_addr(self, addr: str):
        self.__preferred_ip_addr = addr

    def __wait_forever(self):
        self._timestamp('Waiting forever')
        signal.pause()
        os.__exit(int(self.__run_failed))

    def __fail(self, msg: str):
        self._timestamp(f"Run failed: {msg}")
        msg = f'''{msg}
Run:
oc logs -n '{self._namespace()}' '{self._podname()}' -c '{self._container()}'
'''
        self.__do_sync_command('FAIL', msg, timeout=30)
        self.__run_failed = True
        if self.__is_worker:
            os._exit(1)

    def __initialize_timing(self):
        if self.__timing_initialized:
            return
        name = self._idname()
        self._timestamp("About to sync")
        data = self.__do_sync_command('TIME', f'timestamp: %s {name}')
        try:
            [local_sync_start, remote_sync_start, absolute_sync_start,
             remote_sync_base, remote_sync, sync_base_start_time] = self._fsplit(data.decode('ascii'))
        except Exception as err:
            self._timestamp(f"Could not parse response from server: {data}: {err}")
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
        self._timestamp("Timing parameters:")
        for key, val in self.__timing_parameters.items():
            self._timestamp('%-32s %.6f' % (key, val))
            self.__basetime += self.__baseoffset
            self.__crtime += self.__baseoffset
        self.__timing_initialized = True

    def __do_sync_command(self, command: str, token: str = '', timeout: float = None):
        if not self.__enable_sync:
            return
        lcommand = command.lower()
        if lcommand == 'sync' and (token is None or token == ''):
            token = f'{self._ts()} {self.__pod()}-{random.randrange(1000000000)}'
        initial_time = time.time()
        token = f'{command} {token}'.replace('%s', str(time.time()))
        token = ('0x%08x%s' % (len(token), token)).encode()
        while True:
            self._timestamp(f'sync {lcommand} on {self.__synchost}:{self.__syncport}')
            sync_conn = self._connect_to(self.__synchost, self.__syncport, timeout=timeout)
            while len(token) > 0:
                if len(token) > 128:
                    self._timestamp(f'Writing {command}, {len(token)} bytes to sync')
                else:
                    self._timestamp(f'Writing token {token.decode("utf-8")} to sync')
                try:
                    if sync_conn:
                        answer = sync_conn.send(token)
                        if answer <= 0:
                            self._timestamp("Write token failed")
                        else:
                            token = token[answer:]
                    else:
                        self._timestamp("Write token failed: timed out")
                        return None
                except Exception as err:
                    self._timestamp(f'Write token failed: {err}')
                    os._exit(1)
            try:
                answer = sync_conn.recv(1024)
                sync_conn.close()
                self._timestamp(f'sync complete, response {answer.decode("utf-8")}')
                return answer
            except Exception as err:
                if timeout and time.time() - initial_time > timeout:
                    self._timestamp(f'sync failed {err}, timeout expired')
                    return None
                else:
                    self._timestamp(f'sync failed {err}, retrying')

    def __finish(self, status: bool = True, message: str = '', pid: int = os.getpid()):
        if self.__is_worker:
            if message:
                message = f': {message}'
            if status:
                self._timestamp(f"Process {pid} succeeded{message}")
            else:
                self._timestamp(f"ERROR: Process {pid} failed{message}")
                self.__fail(f"ERROR: Process {pid} failed{message}")
            os._exit(int(not status))
        else:
            if status:
                if message:
                    message = f': {message}'
            else:
                if not message:
                    message = 'Unspecified error'
            if status:
                self._timestamp(f"Run succeeded{message}")
            else:
                self.__fail(message)
            if self.__exit_at_end:
                os._exit(int(not status))
            else:
                self.__wait_forever()
        raise Exception("__finish() should not return")
