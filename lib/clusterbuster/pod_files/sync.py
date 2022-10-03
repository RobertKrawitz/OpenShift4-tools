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
import math
import stat


def _get_timestamp(string: str):
    """
    Return a string with a timestamp prepended to the first line
    and any other lines indented
    :param string: String to be timestamped
    :return: Timestamped string
    """
    string = re.sub(r'\n(.*\S.*)', r'\n            \1', string)
    ts = datetime.utcfromtimestamp(ytime()).strftime('%Y-%m-%dT%T.%f')
    return '%s %s\n' % (ts, string)


def timestamp(string: str):
    print(_get_timestamp(string).rstrip(), file=sys.stderr)


def fatal(string: str):
    timestamp(string)
    sys.exit(1)


def ytime():
    global offset_from_controller
    return time.time() + offset_from_controller


def touch(file: str):
    with open(file, "w") as f:
        f.write('')


def clean_numbers(ref):
    """
    Perl to_json encodes infinity as inf and NaN as nan.
    This results in invalid JSON.  It's our responsibility to sanitize
    this up front.
    https://docs.python.org/3.8/library/json.html#infinite-and-nan-number-values
    Also, detect objects that can't be converted to JSON and fail fast
    :param ref: object to be cleaned
    :return: object cleaned of any NaN or infinity values
    """
    def clean_numbers_impl(ref, pathto: str = ''):
        errors = []
        warnings = []
        if isinstance(ref, dict):
            answer = dict()
            for key, val in ref.items():
                a1, e1, w1 = clean_numbers_impl(val, f'{pathto}.{key}')
                answer[key] = a1
                errors.extend(e1)
                warnings.extend(w1)
            return answer, errors, warnings
        elif isinstance(ref, list):
            answer = []
            for index in range(len(ref)):
                a1, e1, w1 = clean_numbers_impl(ref[index], f'{pathto}[{index}]')
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

    [answer, errors, warnings] = clean_numbers_impl(ref)
    if warnings:
        timestamp("\n".join(warnings))
    if errors:
        timestamp('\n' + '\n'.join(errors))
    else:
        return answer


def read_token(stream):
    try:
        prefix = stream.recv(10).decode('ascii').lower()
    except Exception as exc:
        timestamp(f"Unable to read token: {exc}")
        return None
    if len(prefix) != 10:
        timestamp("Unable to read token: short read")
        return None
    m = re.match(r'0x[0-9a-z]{8}', prefix)
    if m:
        bytes_to_read = int(prefix, base=16)
    else:
        timestamp(f"Bad token: {prefix}")
        return None
    answer = ''
    offset = 0
    while bytes_to_read > 0:
        try:
            chunk = stream.recv(bytes_to_read).decode('ascii')
        except Exception as exc:
            timestamp(f"Bad read with {bytes_to_read} left at offset {offset}: {exc}")
        nbytes = len(chunk)
        if nbytes == 0:
            timestamp(f"Short read: got zero bytes with {bytes_to_read} left at {offset}")
            return None
        else:
            answer += chunk
            bytes_to_read -= nbytes
            offset += nbytes
    return answer


def get_port(addr: str = None, port: int = None, backlog=5):
    """
    :param addr: address to listen on, or None for all
    :param port: port to listen on
    :param backlog: listen queue length, default 5
    :return: socket that we are listening on
    """
    if addr is None:
        addr = ''
    try:
        sock = socket.socket()
        sock.bind((addr, port))
        return sock
    except Exception as err:
        fatal(f"Cannot create listener: {err}")


def isdir(path: str):
    try:
        s = os.stat(path)
        return stat.S_ISDIR(s.st_mode)
    except Exception:
        return False


def isfile(path: str):
    try:
        s = os.stat(path)
        return stat.S_ISREG(s.st_mode)
    except Exception:
        return False


def get_controller_timing(timestamp_file: str):
    """
    Normalize time to the run host.  We collect two timestamps on the run host
    bracketing one taken here, giving us an approximate delta between the two
    hosts.  We assume that the second timestamp on the host is taken closer to
    the sync host timestamp on the grounds that setting up the oc exec
    is slower than tearing it down, but in either event, we know what the worst
    case error is.
    """
    while not isfile(timestamp_file):
        time.sleep(0.1)
    with open(timestamp_file, "r", encoding='ascii') as tsfile:
        try:
            controller_json_data = tsfile.read()
        except Exception as error:
            fatal(f"Cannot read data from {tsfile}: {error}")
    timestamp(f"Timestamp data: {controller_json_data}")
    try:
        tsdata = json.loads(controller_json_data)
        tsdata['offset_from_controller'] = tsdata['second_controller_ts'] - tsdata['sync_ts']
    except Exception as error:
        fatal(f"Cannot convert data to JSON: {error}")
    try:
        os.unlink(timestamp_file)
    except Exception:
        pass
    return tsdata


def handle_result(tmp_sync_file_base: str, expected_clients: int, tbuf: str):
    tmp_sync_file = f'{tmp_sync_file_base}-{expected_clients}'
    try:
        with open(tmp_sync_file, 'w') as tmp:
            tmp.write(tbuf.rstrip())
    except Exception as error:
        fatal(f"Can't write to sync file {tmp_sync_file}: {error}")


def reply_timestamp(start_time: float, base_start_time: float, ts_clients: list):
    start = ytime()
    timestamp("Returning client sync start time, sync start time, sync sent time")
    for client in ts_clients:
        time = ytime()
        client_fd, client_ts = client
        tbuf = f"{client_ts} {start_time} {start} {time} {base_start_time}"
        client_fd.send(tbuf.encode('ascii'))
    end = ytime()
    et = end - start
    timestamp(f"Sending sync time took {et} seconds")


def sync_one(sock, tmp_sync_file_base: str, tmp_error_file: str, start_time: float,
             base_start_time: float, expected_clients: int, first_pass: bool):
    timestamp(f"Listening on port {listen_port}")
    try:
        sock.listen(expected_clients)
    except Exception as err:
        fatal(f"listen failed: {err}")
    timestamp(f"Expect {expected_clients} client(s)")
    ts_clients = []
    # Ensure that the client file descriptors do not get gc'ed,
    # closing it prematurely.  This is used when we don't
    # need to send a meaningful reply.  Without this, we do get some
    # failures.
    # Tested with
    # clusterbuster -P synctest --synctest-count=1000 --synctest-cluster-count=3
    #     --precleanup --deployments=10 --cleanup=0
    protected_clients = []
    while expected_clients > 0:
        # Reverse hostname lookup adds significant overhead
        # when using sync to establish the timebase.
        client, address = sock.accept()
        tbuf = read_token(client)
        if not tbuf:
            timestamp(f"Read token from {address} failed")
        protected_clients.append(client)
        command = tbuf[0:4].lower()
        payload = tbuf[4:].lstrip()
        timestamp(f"Accepted connection from {address}, command {command}, payload {len(payload)}")
        if command == 'time':
            if not first_pass:
                timestamp(f"Unexpected request for time sync from {payload}")
                with open(tmp_error_file, "w") as tmp:
                    print(f"Unexpected request for time sync from {payload}", file=tmp_error_file)
                try:
                    os.link(tmp_error_file, error_file)
                except Exception as err:
                    fatal(f"Can't link {tmp_error_file} to {error_file}: {err}")
                timestamp(f"Waiting for error file {error_file} to be removed")
                while isfile(error_file):
                    time.sleep(1)
                os._exit(1)
            ignore, ts, ignore = payload.split()
            ts_clients.append([client, f"{ts} {ytime()}"])
        elif command == 'rslt':
            handle_result(tmp_sync_file_base, expected_clients, payload)
        elif command == 'fail':
            timestamp(f"Detected failure from {address}")
            if tmp_error_file:
                try:
                    with open(tmp_error_file, "w") as tmp:
                        tmp.write(payload)
                except Exception as err:
                    fatal(f"Can't write to {tmp_error_file}: {err}")
                try:
                    os.link(tmp_error_file, error_file)
                except Exception as err:
                    fatal(f"Can't link {tmp_error_file} to {error_file}: {err}")
                timestamp(f"Waiting for error file {error_file} to be removed")
                while isfile(error_file):
                    time.sleep(1)
            else:
                timestamp("Message: {payload}")
            os._exit(1)
        elif command != 'sync':
            timestamp(f"Unknown command from {address}: '{command}'")
        expected_clients -= 1
    if ts_clients:
        reply_timestamp(start_time, base_start_time, ts_clients)
    timestamp("Sync complete")
    sys.exit(0)


offset_from_controller = 0
print(sys.argv, file=sys.stderr)
try:
    sync_file = sys.argv[1]
    error_file = sys.argv[2]
    controller_timestamp_file = sys.argv[3]
    predelay = float(sys.argv[4])
    postdelay = float(sys.argv[5])
    listen_port = int(sys.argv[6])
    expected_clients = int(sys.argv[7])
    initial_expected_clients = int(sys.argv[8])
    sync_count = int(sys.argv[9])
    if initial_expected_clients < 0:
        initial_expected_clients = expected_clients
except Exception as exc:
    timestamp(f"Can't initialize arguments: {exc}")

start_time = time.time()
base_start_time = start_time
original_sync_count = sync_count
timestamp("Clusterbuster sync starting")
sock = get_port(None, listen_port)
if sync_file:
    tmp_sync_file_base = f'{sync_file}-tmp'
else:
    tmp_sync_file_base = None
if error_file:
    tmp_error_file = f'{error_file}-tmp'
else:
    tmp_error_file = None
tmp_sync_files = [f"{tmp_sync_file_base}-{i}" for i in range(1, expected_clients + 1)]

controller_timestamp_data = get_controller_timing(controller_timestamp_file)
timestamp("About to adjust timestamp")
timestamp(f"Max timebase error {controller_timestamp_data['offset_from_controller']}")
start_time += controller_timestamp_data['offset_from_controller']
timestamp(f"Adjusted timebase by {controller_timestamp_data['offset_from_controller']} seconds {base_start_time} => {start_time}")
if sync_count == 0:
    timestamp(f"No synchronization requested; sleeping {postdelay} seconds")
    time.sleep(postdelay)
else:
    timestamp(f"Will sync {sync_count} times")
    first_pass = True
    while sync_count != 0:
        if sync_count > 0:
            sync_count -= 1
        if isfile(tmp_error_file):
            fatal("Job failed, exiting")
        tmp_sync_file = None
        # Ensure that all of the accepted connections get closed by exiting
        # a child process.  This way we don't have to keep track of all of the
        # clients and close them manually.
        try:
            child = os.fork()
        except Exception as exc:
            fatal(f"Fork failed: {exc}")
        if child == 0:
            if first_pass:
                clients = initial_expected_clients
            else:
                clients = expected_clients
            sync_one(sock, tmp_sync_file_base, tmp_error_file, start_time, base_start_time, clients, first_pass)
        else:
            try:
                os.wait()
            except Exception as err:
                fatal(f"Wait failed: {err}")
        if first_pass:
            touch("/tmp/clusterbuster-started")
            if predelay > 0:
                timestamp(f"Waiting {predelay} seconds before start")
                time.sleep(predelay)
            first_pass = False
    touch("/tmp/clusterbuster-finished")
    if postdelay > 0:
        timestamp(f"Waiting {postdelay} seconds before end")
        time.sleep(postdelay)

if isfile(tmp_error_file):
    fatal("Job failed, exiting")

result = {
    'controller_timing': controller_timestamp_data
    }

data = []

if tmp_sync_files:
    for f in tmp_sync_files:
        try:
            with open(f, "r") as fp:
                content = fp.read()
                datum = json.loads(content)
                data.append(datum)
        except Exception as exc:
            timestamp(f"Could not load JSON from {f}: {exc}")
            data.append(dict())
elif not original_sync_count:
    data = [dict() for i in expected_clients]
else:
    timestamp(f"original sync count {original_sync_count}")
result['worker_results'] = data

try:
    with open(tmp_sync_file_base, 'w') as tmp:
        tmp.write(json.dumps(clean_numbers(result)))
except Exception as exc:
    fatal(f"Can't write to sync file {tmp_sync_file_base}: {exc}")
try:
    os.rename(tmp_sync_file_base, sync_file)
except Exception as exc:
    fatal(f"Can't rename {tmp_sync_file_base} to {sync_file}: {exc}")
timestamp(f"Waiting for sync file {sync_file} to be removed")
while isfile(sync_file):
    time.sleep(1)
timestamp(f"Sync file {sync_file} removed, exiting")
sys.exit(0)
