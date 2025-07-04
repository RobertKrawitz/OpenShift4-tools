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
import re
import sys
import subprocess
import signal
import random
import traceback
import shutil
from cb_util import cb_util


class ClusterBusterPodClientException(Exception):
    def __init__(self, *args):
        super().__init__('\n'.join([str(arg) for arg in args]))


class clusterbuster_pod_client(cb_util):
    """
    Python interface to the ClusterBuster pod API
    """

    def __init__(self, initialize_timing_if_needed: bool = True, argv: list = sys.argv, external_sync_only: bool = False):
        # We need to have the nonce very early to initialize.
        super().__init__(no_timestamp=external_sync_only)
        if external_sync_only:
            self.__synchost = os.environ.get('__CB_SYNCHOST')
            self.__syncport = int(os.environ.get('__CB_SYNCPORT'))
            self.__drop_cache_host = os.environ.get('__CB_DROP_CACHE_HOST', None)
            self.__sync_nonce = os.environ.get('__CB_SYNC_NONCE', None)
            try:
                self.__drop_cache_port = int(os.environ.get('__CB_DROP_CACHE_PORT'))
            except Exception:
                self.__drop_cache_port = None
            self.__external_sync_only = True
            self.__enable_sync = True
            self.__pod = os.environ.get('__CB_HOSTNAME', socket.gethostname())
            self.__sync_ns_port = None
            self.__sync_watchdog_port = None
        else:
            self.__external_sync_only = False
            print(f'Args: {" ".join(argv)}', file=sys.stderr)
            # No use in catching errors here, since we may not be sufficiently initialized
            # to signal them back.
            if len(argv) < 9:
                print("clusterbuster_pod_client: incomplete argument list", file=sys.stderr)
                os._exit(1)
            print(f"clusterbuster_pod_client {argv}", file=sys.stderr)
            self.__sync_nonce = argv[1]
            self.__namespace = argv[2]
            self.__container = argv[3]
            self.__basetime = float(argv[4])
            self.__baseoffset = float(argv[5])
            self.__crtime = float(argv[6])
            self.__exit_at_end = self._toBool(argv[7])
            self.__synchost = argv[8]
            self.__syncport = int(argv[9])
            self.__sync_ns_port = int(argv[10])
            self.__sync_watchdog_port = int(argv[11])
            self.__sync_watchdog_timeout = int(argv[12])
            self.__drop_cache_host = argv[13]
            try:
                self.__drop_cache_port = int(argv[14])
            except Exception:
                self.__drop_cache_port = None
            self.__is_worker = False
            self.__start_time = float(time.time())
            self.__enable_sync = True
            self.__host_table = {}
            self.__reported_results = False
            self.__child_idx = -1
            os.environ['__CB_SYNCHOST'] = self.__synchost
            os.environ['__CB_SYNCPORT'] = str(self.__syncport)
            os.environ['__CB_DROP_CACHE_HOST'] = self.__drop_cache_host
            os.environ['__CB_SYNC_NONCE'] = self.__sync_nonce
            os.environ['__CB_DROP_CACHE_PORT'] = str(self.__drop_cache_port) if self.__drop_cache_port else ''
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
                self.__pod = os.environ.get('__CB_HOSTNAME', socket.gethostname())
                self._args = argv[15:]
                self.__timing_parameters = {}
                self.__timing_initialized = False
                if initialize_timing_if_needed:
                    self.__initialize_timing()
                self._set_offset(self.__timing_parameters.get('local_offset_from_sync', 0))
                self.__processes = 1
                self.__requested_ip_addresses = [f'{self.__pod}.{self.__namespace}']
                self._timestamp(f'Ready to start watchdog client in {self.__pod}.{self.__namespace}')
                if self.__enable_sync and self.__sync_watchdog_port is not None and self.__sync_watchdog_port > 0:
                    self._timestamp(f"About to start watchdog client in {self.__pod}.{self.__namespace}")
                    self.__run_watchdog()
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
        pid_hash = dict()
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
                    self._timestamp(f"About to run subprocess {i} (pid {os.getpid()})")
                    try:
                        start_time = self._adjusted_time()
                        user, system = self._cputimes()
                        self.runit(i)
                        if not self.__reported_results:
                            end_time = self._adjusted_time()
                            user, system = self._cputimes(user, system)
                            self._report_results(start_time, end_time, start_time - end_time,
                                                 user, system, {'Note': 'No results provided'})
                        self._timestamp(f"Process {i} (pid {os.getpid()}) complete")
                        self.__finish()
                    except ClusterBusterPodClientException as err:
                        self.__finish(False, message=err)
                    except Exception as err:
                        # If something goes wrong with the workload that isn't caught,
                        # a traceback will likely be useful
                        self.__finish(False, message=f'{err}\n{traceback.format_exc()}')
                    raise Exception("runWorkload should not reach this point!")
                else:
                    pid_hash[child] = i
                    pid_count = pid_count + 1
            except Exception as err:
                self.__finish(False, message=f"Subprocess {i} failed: {err}")
        messages = []
        while pid_count > 0:
            try:
                pid, status = os.wait()
                if status & 255:
                    messages.append(self._timestamp(f"Process {i} (pid {pid}) killed by signal {status & 255}"))
                    try:
                        messages.append(self._run_cmd("dmesg"))
                    except Exception as err:
                        messages.append(f'Cannot retrieve kernel messages: {err}')
                elif status / 256:
                    messages.append(self._timestamp(f"Process {i} (pid {pid}) failed with status {int(status / 256)}"))
                else:
                    self._timestamp(f"Process {i} (pid {pid}) completed successfully")
                pid_count = pid_count - 1
            except Exception as err:
                messages.append(self._timestamp(f'Wait failed: {err}'))
                try:
                    messages.append(self._run_cmd("dmesg"))
                except Exception as err:
                    messages.append(f'Cannot retrieve kernel messages: {err}')
                self.__finish(False, message='\n'.join(messages))
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

    def _drop_cache(self):
        """
        Attempt to drop buffer cache locally and on remote (typically hypervisor)
        :param service: Service for requesting drop cache
        :param port: Port for requesting drop cache
        """
        self._timestamp("Dropping local cache")
        subprocess.run('sync')
        if self.__drop_cache_host and self.__drop_cache_port:
            self._timestamp("Dropping host cache")
            with self._connect_to(self.__drop_cache_host, self.__drop_cache_port) as sock:
                self._timestamp(f"    Connected to {self.__drop_cache_host}:{self.__drop_cache_port}")
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
        components = [self._namespace(), self._podname(), self._container(), str(self.__child_idx)]
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
            'process': self.__child_idx,
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
            answer = json.dumps(self._sanitize_json(answer))
        except TypeError as exc:
            self.__fail(f"Cannot convert results to JSON: {exc}")
        except Exception as exc:
            self.__fail(f"Unexpected error when converting results to JSON: {exc}")
        self.__do_sync_command('RSLT', answer)
        self.__reported_results = True

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

    def _get_drop_cache_port(self):
        return self.__drop_cache_port

    def _run_command(self, *cmd):
        """
        Run specified command
        :param cmd: Command to be run
        :return: process status, stdout, stderr
        """
        command = []
        for arg in cmd:
            if isinstance(arg, list):
                command.extend(arg)
            elif isinstance(arg, dict):
                for k, v in arg.items():
                    command.append(str(k))
                    command.append(str(v))
            else:
                command.append(str(arg))
        self._timestamp(f"Running {' '.join(command)}")
        process = subprocess.run(command, capture_output=True, text=True)
        return (True if process.returncode == 0 else False), process.stdout, process.stderr

    def _cleanup_tree(self, tree, doit: bool = True, sync: bool = True):
        """
        Clean up an entire directory tree other than the root.  Errors are ignored.
        This is safe to call from multiple concurrent callers
        This routine attempts to remove all subdirectories and files once.
        It then syncs back to the controller and then checks that the tree
        is in fact empty.
        If optional parameter doit is False, don't actually perform the cleanup.
        This is useful if there are multiple processes that will be run as part
        of the workload, when it's only necessary for one to perform the cleanup.
        All processes should call cleanup_tree so that appropriate synchronization
        is done.
        :param tree: Filesystem tree to be cleaned up
        :param skip: Skip actually doing anything.
        :return: True if cleanup succeeded, False otherwise
        """
        self._timestamp(f"Cleaning up {tree}")
        if doit and os.path.exists(tree):
            for f in os.listdir(tree):
                self._timestamp(f"Looking at {f}")
                if f == '.' or f == '..':
                    pass
                f = os.path.join(tree, f)
                self._timestamp(f"Now looking at {f}")
                try:
                    if os.path.isdir(f):
                        self._timestamp(f"Attempting to clean up subdir {f}")
                        shutil.rmtree(f, True)
                    else:
                        self._timestamp(f"Attempting to clean up file {f}")
                        os.remove(f)
                except (FileNotFoundError, PermissionError):
                    pass
        if sync:
            self._sync_to_controller(f"Cleanup {tree}")
        if doit and os.path.exists(tree):
            for f in os.listdir(tree):
                if f == '.' or f == '..':
                    pass
                return False
        return True

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

    def _resolve_host(self, addr):
        if not self.__is_raw_ip(addr) and ('sync' not in addr or '@' in addr):
            if '@' not in addr:
                addr = f'eth0@{addr}'
            addr = f'{addr}.{self.__namespace}'
            answer = self.__request_ip_addresses([addr])
            if addr in answer:
                return answer[addr]
            else:
                raise socket.gaierror("Unable to resolve {addr}")
        else:
            return super()._resolve_host(addr)

    def __is_raw_ip(self, addr):
        return re.search(r'(^|@)?(([0-9]{1,3}\.){3}[0-9]{1,3}$)', addr) is not None

    def __request_ip_addresses(self, addresses: list):
        answer = {}
        request = {'rqst': []}
        for if_addr in addresses:
            if if_addr in self.__host_table:
                self._timestamp(f"Found cached {if_addr} => {self.__host_table[if_addr]}")
                answer[if_addr] = self.__host_table[if_addr]
            else:
                request['rqst'].append(if_addr)
        if len(request['rqst']) > 0 and self.__sync_ns_port > 0:
            ns_answer = json.loads(self.__do_sync_command('nsrq', json.dumps(request), port=self.__sync_ns_port))
            self._timestamp(f"Requested addresses {addresses}, got {ns_answer}")
            for if_addr, addr in ns_answer.items():
                answer[if_addr] = addr
                self.__host_table[if_addr] = addr
        return answer

    def __initialize_timing(self):
        if self.__timing_initialized:
            return
        name = self._idname()
        self._timestamp("About to sync")
        request = {'timestamp': '%s', 'name': name, 'have': {}}
        for ifname, addr in self._get_ip_addresses().items():
            request['have'][f'{ifname}@{self.__pod}.{self.__namespace}'] = addr
        data = self.__do_sync_command('TNET', json.dumps(request))
        try:
            reply = json.loads(data.decode('ascii'))
            local_presync_start = reply['client_ts']
            remote_sync_start = reply['request_time']
            absolute_sync_start = reply['start_time']
            remote_sync_base = reply['base_start_time']
            remote_sync = reply['reply_start']
            sync_base_start_time = reply['reply_time']
        except Exception as err:
            self._timestamp(f"Could not parse response from server: {data}: {err}")
            os._exit(1)
        local_sync_start = self._get_initial_connect_time()
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
            'local_presync_start': local_presync_start,
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
        json.dump(self.__timing_parameters, sys.stderr)
        for key, val in self.__timing_parameters.items():
            self._timestamp('%-32s %f' % (key, val))
            self.__basetime += self.__baseoffset
            self.__crtime += self.__baseoffset
        self.__timing_initialized = True

    def __run_watchdog(self):
        try:
            child = os.fork()
        except Exception as err:
            print(f'Fork for watchdog failed: {err}', file=sys.stderr)
        if child == 0:
            firsttime = True
            while True:
                try:
                    if not firsttime:
                        time.sleep(self.__sync_watchdog_timeout)
                    firsttime = False
                    self._timestamp("About to pat the watchdog")
                    with self._connect_to(self.__synchost, self.__sync_watchdog_port):
                        pass
                except Exception:
                    pass

    def __do_sync_command(self, command: str, token: str = '', timeout: float = None, port: int = None):
        if not self.__enable_sync:
            return
        if not port:
            port = self.__syncport
        lcommand = command.lower()
        if lcommand == 'sync' and (token is None or token == ''):
            token = f'{self._ts()} {self.__pod}-{random.randrange(1000000000)}'
        token = f'{self.__sync_nonce} {lcommand} {token}'.replace('"%s"', str(time.time()))
        try:
            return self._send_message(self.__synchost, port, token, timeout=timeout)
        except Exception as err:
            self._timestamp(f"Unable to send sync message: {err}")
            os._exit(1)

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
