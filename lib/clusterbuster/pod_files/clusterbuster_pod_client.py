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
import traceback
import stat
from resource import getrusage, RUSAGE_SELF, RUSAGE_CHILDREN


class clusterbuster_pod_client:
    """
    Python interface to the ClusterBuster pod API
    """

    def __init__(self, initialize_timing_if_needed: bool = True, argv: list = sys.argv):
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
        self.__exit_at_end = clusterbuster_pod_client._toBool(argv[6])
        self.__synchost = argv[7]
        self.__syncport = int(argv[8])
        self.__is_worker = False
        self.__start_time = float(time.time())
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
            self.__child_idx = None
            self.__processes = 1
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
        self._timestamp(f'{self.__run_cmd("lscpu")}\n{self.__run_cmd("dmesg")}')
        if messages:
            self.__finish(False, message='\n'.join(messages))
        else:
            self.__finish()

    @staticmethod
    def _toBool(arg, defval: bool = None):
        """
        Parse a string or numerical argument as a bool, based on the following rules:
        - 0,"0", false, no => False
        - non-zero number or string converted to number, true, yes => True
        - Array or hash, empty => False, non-empty => True
        - Anything else, return default value
        :param arg: item to be evaluated
        :return: conversion to bool
        """
        if isinstance(arg, (bool, int, float, list, dict)):
            return bool(arg)
        if isinstance(arg, str):
            arg = arg.lower()
            if arg == 'true' or arg == 'y' or arg == 'yes':
                return True
            elif arg == 'false' or arg == 'n' or arg == 'no':
                return False
            try:
                arg1 = int(arg)
                return arg1 != 0
            except Exception:
                pass
        if defval is not None:
            return defval
        raise ValueError(f'Cannot parse "{arg}" as a boolean value')

    @staticmethod
    def _toBools(*args):
        """
        Split a list of bools, or comma or space separated string of bools,
        into a list of bools.  See _toBool.
        """
        return [clusterbuster_pod_client._toBool(item) for sublist in args for item in re.split(r'[,\s]+', sublist.strip())]

    @staticmethod
    def _toSize(arg: str):
        """
        Parse a size consisting of a decimal number with an optional
        suffix of k, m, g, or t.  If the suffix is followed by 'i',
        the resulting number is treated as binary (powers of 2**10),
        otherwise decimal (powers of 10**3)
        """
        if isinstance(arg, int) or isinstance(arg, float):
            return int(arg)
        m = re.match(r'(-?[0-9]+(\.[0-9]+)?)(([kmgt]?)(i?)(b?)?)?', arg.lower())
        if m:
            mantissa = float(m.group(1))
            modifier = m.group(4)
            binary = bool(m.group(5))
            base = 0
            if modifier == 'k':
                base = 1
            elif modifier == 'm':
                base = 2
            elif modifier == 'g':
                base = 3
            elif modifier == 't':
                base = 4
            if binary:
                return int(mantissa * (1024 ** base))
            else:
                return int(mantissa * (1000 ** base))
        else:
            raise Exception(f"Unparseable number '{arg}'")

    @staticmethod
    def _toSizes(*args):
        """
        Split a list of sizes, or comma or space separated string of sizes,
        into a list of sizes.  See _toSize.
        """
        return [clusterbuster_pod_client._toSize(item) for sublist in args for item in re.split(r'[,\s]+', sublist.strip())]

    @staticmethod
    def _splitStr(regexp: str, arg: str):
        """
        Split a string per the specified regexp.  If the arg is empty,
        return an empty list (re.split() returns a single element for
        an empty string)
        """
        if arg:
            return re.split(regexp, str(arg))
        else:
            return []

    def _verbose(self):
        """
        Should we be verbose?
        :return: whether we should print verbose messages
        """
        return clusterbuster_pod_client._toBool(os.environ.get('VERBOSE', 0))

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

    def _cputimes(self, olduser: float = 0, oldsys: float = 0):
        """
        Return the user and system CPU times, including self and children
        :return: system and user times, in seconds
        """
        r_self = getrusage(RUSAGE_SELF)
        r_children = getrusage(RUSAGE_CHILDREN)
        return (r_self.ru_utime + r_children.ru_utime - olduser, r_self.ru_stime + r_children.ru_stime - oldsys)

    def _cputime(self, old: float = 0):
        """
        Return the total CPU, including self and children
        :return: total CPU time, in seconds
        """
        r_self = getrusage(RUSAGE_SELF)
        r_children = getrusage(RUSAGE_CHILDREN)
        return r_self.ru_utime + r_children.ru_utime + r_self.ru_stime + r_children.ru_stime - old

    def _adjusted_time(self, otime: float = 0):
        """
        Return system time normalized to the host time
        :return: System time, normalized to the host time
        """
        if 'xtime_adjustment' in self.__timing_parameters:
            return time.time() - self.__timing_parameters['xtime_adjustment'] - otime
        else:
            return time.time() - otime

    def _get_timestamp(self, string: str):
        """
        Return a string with a timestamp prepended to the first line
        and any other lines indented
        :param string: String to be timestamped
        :return: Timestamped string
        """
        string = re.sub(r'\n(.*\S.*)', r'\n            \1', string)
        return '%7d %s %s\n' % (os.getpid(), self.__ts(), string)

    def _timestamp(self, string):
        """
        Timestamp a string and print it to stderr
        :param string: String to be printed to stderr with timestamp attached
        """
        print(self._get_timestamp(str(string)), file=sys.stderr, end='')

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

    def _isdir(self, path: str):
        try:
            s = os.stat(path)
            return stat.S_ISDIR(s.st_mode)
        except Exception:
            return False

    def _isfile(self, path: str):
        try:
            s = os.stat(path)
            return stat.S_ISREG(s.st_mode)
        except Exception:
            return False

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

    def _resolve_host(self, hostname: str):
        """
        Resolve a host name to dotted quad IP address, retrying as needed
        :param hostname: Host name to resolve
        :return: Dotted-quad string representation of hostname
        """
        while True:
            try:
                return socket.gethostbyname(hostname)
            except socket.gaierror as err:
                self._timestamp(f"gethostbyname({hostname}) failed: {err}")
                time.sleep(1)

    def _connect_to(self, addr: str = None, port: int = None, timeout: float=None):
        """
        Connect to specified address and port.
        :param addr: address to connect to, default the sync host
        :param port: port to connect to, default the sync port
        :return: connected socket
        """
        if addr is None:
            addr = self.__synchost
        if port is None:
            port = self.__syncport
        retries = 0
        initial_time = time.time()
        while True:
            try:
                try:
                    sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
                except Exception as err:
                    self._timestamp(f"Cannot create socket: {err}")
                    os._exit(1)
                # We call gethostbyname() each time through the loop because
                # the remote hostname might not exist immediately.
                sock.connect((addr, port))
                if retries:
                    self._timestamp(f"Connected after {retries} retries")
                return sock
            except Exception as err:
                if timeout and time.time() - initial_time > timeout:
                    sock.close()
                    return None
                if retries < 10:
                    self._timestamp(f"Cannot connect to {addr} on port {port}: {err}")
                elif retries == 10:
                    self._timestamp("Printing no further messages")
                time.sleep(1)
                retries = retries + 1
            sock.close()

    def _listen(self, addr: str = None, port: int = None, backlog=5):
        """
        Listen on specified port and optoinal address
        :param addr: address to listen on, or None for all
        :param port: port to listen on
        :param backlog: listen queue length, default 5
        :return: socket that we are listening on
        """
        if addr is None:
            addr = ''
        try:
            sock = socket.socket()
            sock.bind(('', port))
            sock.listen(backlog)
            return sock
        except Exception as err:
            self._timestamp(f"Cannot create listener: {err}")
            os._exit(1)

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
            answer = json.dumps(self.__clean_numbers(answer))
        except Exception as exc:
            self.__fail(f"Cannot convert results to JSON: {exc}")
        self.__do_sync_command('RSLT', answer)

    def _sync_to_controller(self, token: str = None):
        """
        Perform a sync to the controller
        :param token: Optional string to use for sync; None to generate one
        """
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

    def __run_cmd(self, cmd):
        """
        Attempt to run the specified command
        :param command: Command to be run (string or list)
        :return: Timestamped stdout of the command
        """
        try:
            answer = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            message = answer.stdout.decode("ascii")
            if message:
                return f'{cmd} output:\n{message}'
            else:
                return f'{cmd} produced no output'
        except Exception as err:
            return f"Can't run {cmd}: {err}"

    def __clean_numbers(self, ref):
        """
        Perl to_json encodes infinity as inf and NaN as nan.
        This results in invalid JSON.  It's our responsibility to sanitize
        this up front.
        https://docs.python.org/3.8/library/json.html#infinite-and-nan-number-values
        Also, detect objects that can't be converted to JSON and fail fast
        :param ref: object to be cleaned
        :return: object cleaned of any NaN or infinity values
        """
        def __clean_numbers_impl(ref, pathto: str = ''):
            errors = []
            warnings = []
            if isinstance(ref, dict):
                answer = dict()
                for key, val in ref.items():
                    a1, e1, w1 = __clean_numbers_impl(val, f'{pathto}.{key}')
                    answer[key] = a1
                    errors.extend(e1)
                    warnings.extend(w1)
                return answer, errors, warnings
            elif isinstance(ref, list):
                answer = []
                for index in range(len(ref)):
                    a1, e1, w1 = __clean_numbers_impl(ref[index], f'{pathto}[{index}]')
                    answer.append(a1)
                    errors.extend(e1)
                    warnings.extend(w1)
                return answer, errors, warnings
            elif isinstance(ref, float) and (math.isnan(ref) or math.isinf(ref)):
                warnings.append(f"Warning: illegal float value {ref} at {pathto} converted to None")
                return None, errors, warnings
            elif ref is None or isinstance(ref, float) or isinstance(ref, str) or isinstance(ref, int):
                return ref, errors, warnings
            else:
                errors.append(f"    Object {pathto} ({ref}) cannot be serialized")
                return ref, errors, warnings

        [answer, errors, warnings] = __clean_numbers_impl(ref)
        if warnings:
            self._timestamp("\n".join(warnings))
        if errors:
            raise Exception('\n' + '\n'.join(errors))
        else:
            return answer

    def __ts(self):
        localoffset = self.__timing_parameters.get('local_offset_from_sync', 0)
        return datetime.utcfromtimestamp(time.time() - localoffset).strftime('%Y-%m-%dT%T.%f')

    def __fsplit(self, string: str):
        return [float(s) for s in string.split()]

    def __initialize_timing(self):
        if self.__timing_initialized:
            return
        name = self._idname()
        self._timestamp("About to sync")
        data = self.__do_sync_command('TIME', f'timestamp: %s {name}')
        try:
            [local_sync_start, remote_sync_start, absolute_sync_start,
             remote_sync_base, remote_sync, sync_base_start_time] = self.__fsplit(data.decode('ascii'))
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
        lcommand = command.lower()
        if lcommand == 'sync' and (token is None or token == ''):
            token = f'{self.__ts()} {self.__pod()}-{random.randrange(1000000000)}'
        initial_time = time.time()
        token = f'{command} {token}'.replace('%s', str(time.time()))
        token = ('0x%08x%s' % (len(token), token)).encode()
        while True:
            self._timestamp(f'sync {lcommand} on {self.__synchost}:{self.__syncport}')
            sync_conn = self._connect_to(timeout=timeout)
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
