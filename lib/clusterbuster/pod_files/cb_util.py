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

import socket
import re
import os
import fcntl
import struct
from datetime import datetime
import time
import sys
import stat
import math
import subprocess
from resource import getrusage, RUSAGE_SELF, RUSAGE_CHILDREN


class cb_util:
    """
    Miscellaneous utilities for ClusterBuster shared (at least in principle)
    between the controller and clients
    """
    def __init__(self, offset: float = 0, no_timestamp: bool = False):
        # If we're pid 1, we're the container init.
        # We need to wait() for anything we don't care about so zombies
        # don't build up.  It must specifically be pid 1 that wait()s
        # so we fork as early as possible.
        if os.getpid() == 1:
            try:
                child = os.fork()
            except Exception as err:
                print(f"Fork failed: {err}", file=sys.stderr)
                os.exit(1)
            if child != 0:
                while True:
                    # We don't ever want to inadvertently exit from an
                    # exception!
                    try:
                        pid, status = os.wait()
                        try:
                            wstatus = os.waitstatus_to_exitcode(status)
                        except ValueError:
                            print(f'(pid 1) Got unexpected exit status {status} from {pid}')
                            wstatus = 1
                        except ChildProcessError:
                            pass
                        except Exception as exc:
                            print(f'(pid 1) Caught exception {exc}, continuing')
                        # If our worker exits, that's our cue to terminate.
                        if pid == child:
                            os.exit(wstatus)
                        else:
                            print(f'(pid 1) Caught exit from {pid} status {wstatus}', file=sys.stderr)
                    except ChildProcessError:
                        time.sleep(1)
                    except Exception as exc:
                        # Maybe a bit too paranoid here, but...
                        try:
                            print(f'(pid 1) Caught exception {exc}, continuing')
                        except Exception:
                            pass
        self.__offset = offset
        self.__no_timestamp = no_timestamp
        self.__initial_connect_time = None

    def _set_offset(self, offset: float = 0):
        old_offset = self.__offset
        self.__offset = offset
        return old_offset

    def _get_initial_connect_time(self):
        """
        Return the local timestamp immediately prior to the first
        successful attempt to connect to the sync controller.  This
        should be used for computing the sync rtt.
        """
        return self.__initial_connect_time

    def _ts(self, t=None):
        return datetime.utcfromtimestamp((t if t is not None else time.time()) - self.__offset).strftime('%Y-%m-%dT%T.%f')

    def _get_timestamp(self, string: str = ''):
        """
        Return a string with a timestamp prepended to the first line
        and any other lines indented
        :param string: String to be timestamped
        :return: Timestamped string
        """
        if self.__no_timestamp:
            return f'{string}\n'
        else:
            string = re.sub(r'\n(.*\S.*)', r'\n            \1', string)
            return '%7d %s %s\n' % (os.getpid(), self._ts(), string)

    def _timestamp(self, string):
        """
        Timestamp a string and print it to stderr
        :param string: String to be printed to stderr with timestamp attached
        """
        print(self._get_timestamp(str(string)), file=sys.stderr, end='')

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

    def _toBool(self, arg, defval: bool = None):
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

    def _toBools(self, *args):
        """
        Split a list of bools, or comma or space separated string of bools,
        into a list of bools.  See _toBool.
        """
        return [self._toBool(item) for sublist in args for item in re.split(r'[,\s]+', sublist.strip())]

    def _toSize(self, arg):
        """
        Parse a size consisting of a decimal number with an optional
        suffix of k, m, g, or t.  If the suffix is followed by 'i',
        the resulting number is treated as binary (powers of 2**10),
        otherwise decimal (powers of 10**3)
        """
        if isinstance(arg, (int, float, bool)):
            return int(arg)
        elif arg is None:
            return 0
        elif isinstance(arg, str):
            m = re.match(r'(-?[0-9]+(\.[0-9]+)?)(([kmgtpezy]?)(i?)(b?)?)?', arg.lower())
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
                elif modifier == 'p':
                    base = 5
                elif modifier == 'e':
                    base = 6
                elif modifier == 'z':
                    base = 7
                elif modifier == 'y':
                    base = 8
                if binary:
                    return int(mantissa * (1024 ** base))
                else:
                    return int(mantissa * (1000 ** base))
            else:
                raise ValueError(f"Unparseable number '{arg}'")
        else:
            raise ValueError(f"Argument must be integer, float, or string: {arg}")

    def _toSizes(self, *args):
        """
        Split a list of sizes, or comma or space separated string of sizes,
        into a list of sizes.  See _toSize.
        """
        return [self._toSize(item) for sublist in args for item in re.split(r'[,\s]+', sublist.strip())]

    def _splitStr(self, regexp: str, arg: str):
        """
        Split a string per the specified regexp.  If the arg is empty,
        return an empty list (re.split() returns a single element for
        an empty string)
        """
        if arg:
            return re.split(regexp, str(arg))
        else:
            return []

    def _clean_numbers(self, ref):
        """
        Perl to_json encodes infinity as inf and NaN as nan.
        This results in invalid JSON.  It's our responsibility to sanitize
        this up front.
        https://docs.python.org/3.8/library/json.html#infinite-and-nan-number-values
        Also, detect objects that can't be converted to JSON and fail fast
        :param ref: object to be cleaned
        :return: object cleaned of any NaN or infinity values
        """
        def _clean_numbers_impl(ref, pathto: str = ''):
            errors = []
            warnings = []
            if isinstance(ref, dict):
                answer = dict()
                for key, val in ref.items():
                    a1, e1, w1 = _clean_numbers_impl(val, f'{pathto}.{key}')
                    answer[key] = a1
                    errors.extend(e1)
                    warnings.extend(w1)
                return answer, errors, warnings
            elif isinstance(ref, list):
                answer = []
                for index in range(len(ref)):
                    a1, e1, w1 = _clean_numbers_impl(ref[index], f'{pathto}[{index}]')
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

        [answer, errors, warnings] = _clean_numbers_impl(ref)
        if warnings:
            self._timestamp("\n".join(warnings))
        if errors:
            raise Exception('\n' + '\n'.join(errors))
        else:
            return answer

    def _fsplit(self, string: str):
        return [float(s) for s in string.split()]

    def _run_cmd(self, cmd):
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

    def _connect_to(self, addr: str, port: int, timeout: float = None):
        """
        Connect to specified address and port.
        :param addr: address to connect to
        :param port: port to connect to
        :return: connected socket
        """
        retries = 0
        initial_time = time.time()
        first_start = self._get_initial_connect_time()
        while True:
            try:
                try:
                    sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
                except Exception as err:
                    self._timestamp(f"Cannot create socket: {err}")
                    os._exit(1)
                # We call gethostbyname() each time through the loop because
                # the remote hostname might not exist immediately.
                caddr = self._resolve_host(addr)
                if first_start is None:
                    self.__initial_connect_time = time.time()
                sock.connect((caddr, port))
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

    def _get_port(self, port: int, addr: str = None):
        """
        :param addr: address to bind
        :param port: port to bind to
        :return: socket that we have bound
        """
        if addr is None:
            addr = ''
        sock = socket.socket()
        sock.bind((addr, port))
        return sock

    def _listen(self, port: int = None, addr: str = None, sock: socket = None, backlog: int = 5):
        """
        Listen on specified port and optoinal address
        :param port: port to listen on.  Either port or sock, but not both, must be provided.
        :param addr: address to listen on, or None for all
        :param sock: socket to listen on.  Either port or sock, but not both, must be provided.
        :param backlog: listen queue length, default 5
        :return: socket that we are listening on
        """
        if port is None and sock is None:
            raise ValueError("Either a port or a socket must be provided")
        elif port is not None and sock is not None:
            raise ValueError("Only one of a port or a socket must be provided")
        while True:
            try:
                if sock is None:
                    sock = self._get_port(port, addr)
                sock.listen(backlog)
                return sock
            except Exception as exc:
                self._timestamp(f"Listen failed {exc}, will retry after 10 seconds")
                time.sleep(10)

    def _resolve_host(self, hostname: str):
        """
        Resolve a host name to dotted quad IP address, retrying as needed
        :param hostname: Host name to resolve
        :return: Dotted-quad string representation of hostname
        """
        if re.match(r'([0-9]{1,3}\.){3}[0-9]{1,3}', hostname):
            return hostname
        while True:
            try:
                return socket.gethostbyname(hostname)
            except socket.gaierror as err:
                self._timestamp(f"gethostbyname({hostname}) failed: {err}")
                time.sleep(1)

    def _send_message(self, host: str, port: int, token: str, timeout: float = None):
        initial_time = time.time()
        token = ('0x%08x%s' % (len(token), token)).encode()
        while True:
            self._timestamp(f'sync {port}:{port}')
            sync_conn = self._connect_to(host, port, timeout=timeout)
            while len(token) > 0:
                if len(token) > 128:
                    self._timestamp(f'Writing {len(token)} bytes to sync')
                else:
                    self._timestamp(f'Writing token {token.decode("utf-8")} to sync')
                if sync_conn:
                    answer = sync_conn.send(token)
                    if answer <= 0:
                        self._timestamp("Write token failed")
                    else:
                        token = token[answer:]
                else:
                    self._timestamp("Write token failed: timed out")
                    return None
            try:
                answer = sync_conn.recv(1024)
                self._timestamp(f'sync complete, response {answer.decode("utf-8")}')
                return answer
            except Exception as err:
                if timeout and time.time() - initial_time > timeout:
                    self._timestamp(f'sync failed {err}, timeout expired')
                    return None
                else:
                    self._timestamp(f'sync failed {err}, retrying')
            finally:
                sync_conn.close()

    def _get_primary_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        try:
            # doesn't even have to be reachable
            s.connect(('10.254.254.254', 1))
            ipaddr = s.getsockname()[0]
        except Exception:
            ipaddr = '127.0.0.1'
        finally:
            s.close()
        return ipaddr

    def _get_ip_addresses(self):
        answers = {}
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        with open('/proc/net/dev', 'r') as f:
            # Taken from psutil.  That package is not universally installed
            # so we'll write our own.
            lines = f.readlines()
            for line in lines:
                end = line.rfind(':')
                if end > 0:
                    ifname = line[:end].strip()
                    if ifname != 'lo':
                        try:
                            answers[ifname] = socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915,
                                                                           struct.pack('256s', ifname.encode('ascii')))[20:24])
                        except Exception:
                            pass
        return answers
