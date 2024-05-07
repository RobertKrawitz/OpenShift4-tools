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
import re
import json
import os
import sys
from cb_util import cb_util

offset_from_controller = 0
timebase = cb_util(offset_from_controller)
nameserver_pid = None
sync_nonce = None


def kill_nameserver(timebase: cb_util):
    global nameserver_pid
    if nameserver_pid:
        timebase._timestamp("Killing nameserver")
        os.kill(nameserver_pid, 9)


def fatal(string: str):
    timebase._timestamp(string)
    kill_nameserver
    sys.exit(1)


def ytime():
    global offset_from_controller
    return time.time() + offset_from_controller


def touch(file: str):
    with open(file, "w") as f:
        f.write('')


class nameserver:
    """
    Simplistic nameserver for ClusterBuster workloads
    """
    def __init__(self, timebase: cb_util, port: int, backlog: int = 5):
        self.timebase = timebase
        self.addrs = dict()
        self.requests = dict()
        self.clients = dict()
        try:
            self.sock = timebase._listen(port=port, backlog=backlog)
        except Exception as err:
            self.fatal(f"listen failed: {err}")

    def timestamp(self, string):
        self.timebase._timestamp("Nameserver: " + str(string))

    def fatal(self, string: str):
        self.timestamp(string)
        sys.exit(1)

    def satisfy_requests(self):
        requestors_satisfied = list()
        for addr, req in self.requests.items():
            requests_satisfied = list()
            for want in req['want'].keys():
                if want in self.addrs:
                    self.timestamp(f"    Request from {addr} for {want} => {self.addrs[want]}")
                    self.requests[addr]['have'][want] = self.addrs[want]
                    requests_satisfied.append(want)
            if requests_satisfied:
                for want in requests_satisfied:
                    del self.requests[addr]['want'][want]
                if not self.requests[addr]['want']:
                    jdata = json.dumps(self.requests[addr]['have'])
                    self.timestamp(f"        All requests from {addr} are satisfied: {jdata}, sending")
                    self.clients[addr].send(jdata.encode('ascii'))
                    self.clients[addr].close()
                    del self.clients[addr]
                    requestors_satisfied.append(addr)
        if requestors_satisfied:
            for requestor in requestors_satisfied:
                del self.requests[requestor]

    def get_command(self):
        client, address = self.sock.accept()
        try:
            tbuf = read_token(client)
            nonce, tbuf = tbuf.split(' ', 1)
            if nonce != sync_nonce:
                self.timestamp(f"Received request with incorrect nonce {nonce} from {address}: {tbuf}")
                return None, None, None
            command = tbuf[0:4].lower()
            payload = tbuf[4:].lstrip()
            self.timestamp(f"Accepted connection from {address}, command {command}, payload {payload}")
            json_payload = json.loads(payload)
            if command != 'nsrq':
                raise ValueError(f"Unexpected command {command}")
        except Exception as exc:
            self.timestamp(f"Could not read command from {client} at {address}: {exc}")
            client.close()
            return
        return client, address, json_payload

    def process_command(self):
        try:
            client, address, json_payload = self.get_command()
            if client is None and address is None and json_payload is None:
                return
        except Exception as exc:
            self.timestamp(f"Unable to read command: {exc}")
            return
        for command, args in json_payload.items():
            if command == 'have':
                if not isinstance(args, dict):
                    self.timestamp(f"have payload should be dict, is {args}")
                    continue
                for name, ipaddr in args.items():
                    self.timestamp(f"    {address} offers {name} at {ipaddr}")
                    self.addrs[name] = ipaddr
            elif command == 'rqst':
                if not isinstance(args, list):
                    self.timestamp(f"rqst payload should be list, is {args}")
                    continue
                if address not in self.requests:
                    self.requests[address] = {
                        'have': {},
                        'want': {}
                        }
                for name in args:
                    if address not in self.clients:
                        self.clients[address] = client
                    self.requests[address]['want'][name] = None
            else:
                self.timestamp(f"Unknown command from {address}: '{command}'")

    def run(self):
        while True:
            self.process_command()
            self.satisfy_requests()


def read_token(stream):
    prefix = stream.recv(10).decode('ascii').lower()
    if len(prefix) == 0:
        return None
    if len(prefix) != 10:
        raise ValueError("Unable to read token: short read")
    m = re.match(r'0x[0-9a-z]{8}', prefix)
    if m:
        bytes_to_read = int(prefix, base=16)
    else:
        raise ValueError(f"Bad token: {prefix}")
    answer = ''
    offset = 0
    while bytes_to_read > 0:
        try:
            chunk = stream.recv(bytes_to_read).decode('ascii')
        except Exception as exc:
            raise ValueError(f"Bad read with {bytes_to_read} left at offset {offset}: {exc}")
        nbytes = len(chunk)
        if nbytes == 0:
            raise ValueError(f"Short read: got zero bytes with {bytes_to_read} left at {offset}")
        else:
            answer += chunk
            bytes_to_read -= nbytes
            offset += nbytes
    return answer


def get_controller_timing(timestamp_file: str):
    """
    Normalize time to the run host.  We collect two timestamps on the run host
    bracketing one taken here, giving us an approximate delta between the two
    hosts.  We assume that the second timestamp on the host is taken closer to
    the sync host timestamp on the grounds that setting up the oc exec
    is slower than tearing it down, but in either event, we know what the worst
    case error is.
    """
    while not timebase._isfile(timestamp_file):
        time.sleep(0.1)
    with open(timestamp_file, "r", encoding='ascii') as tsfile:
        try:
            controller_json_data = tsfile.read()
        except Exception as error:
            fatal(f"Cannot read data from {tsfile}: {error}")
    timebase._timestamp(f"Timestamp data: {controller_json_data}")
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


def reply_timestamp(ts_clients: list):
    start = ytime()
    timebase._timestamp("Returning client sync start time, sync start time, sync sent time")
    for client in ts_clients:
        client_fd, client_ts = client
        client_ts['reply_start'] = start
        client_ts['reply_time'] = ytime()
        client_fd.send(json.dumps(client_ts).encode('ascii'))
    end = ytime()
    et = end - start
    timebase._timestamp(f"Sending sync time took {et} seconds")


def fail_hard(payload: str):
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
        timebase._timestamp(f"Waiting for error file {error_file} to be removed")
        while timebase._isfile(error_file):
            time.sleep(1)
    else:
        timebase._timestamp("Message: {payload}")
    os._exit(1)


def sync_one(sock, tmp_sync_file_base: str, tmp_error_file: str, start_time: float,
             base_start_time: float, expected_clients: int, first_pass: bool):
    timebase._timestamp(f"Listening on port {listen_port}, expect {expected_clients} client{'' if expected_clients == 1 else 's'}")
    try:
        timebase._listen(sock=sock, backlog=expected_clients)
    except Exception as err:
        fatal(f"listen failed: {err}")
    ts_clients = []
    net_clients = {}
    # Ensure that the client file descriptors do not get gc'ed,
    # closing it prematurely.  This is used when we don't
    # need to send a meaningful reply.  Without this, we do get some
    # failures.
    # Tested with
    # clusterbuster -P synctest --synctest-count=1000 --synctest-cluster-count=3
    #     --precleanup --deployments=10 --cleanup=0
    protected_clients = []
    expected_command = None
    while expected_clients > 0:
        # Reverse hostname lookup adds significant overhead
        # when using sync to establish the timebase.
        client, address = sock.accept()
        tbuf = read_token(client)
        if not tbuf:
            timebase._timestamp(f"Read token from {address} failed")
            continue
        try:
            nonce, tbuf = tbuf.split(' ', 1)
        except Exception as exc:
            timebase._timestamp(f"Could not parse token {tbuf}: {exc}")
            continue
        # Don't acknowledge replies with incorrect nonce
        if nonce != sync_nonce:
            timebase._timestamp(f"Received request with incorrect nonce {nonce} from {address}: {tbuf}")
            continue
        protected_clients.append(client)
        command = tbuf[0:4].lower()
        if expected_command:
            if command != expected_command:
                fatal(f"Unexpected command {command} from {address}, expected {expected_command}")
        else:
            expected_command = command
        payload = tbuf[4:].lstrip()
        timebase._timestamp(f"Accepted connection from {address}, command {command}, payload {len(payload)}")
        if command == 'time' or command == 'tnet':
            timebase._timestamp(f"Time request {payload}")
            if first_pass:
                if command == 'tnet':
                    try:
                        jdata = json.loads(payload)
                        ts = jdata['timestamp']
                        if 'have' in jdata and isinstance(jdata['have'], dict):
                            for name, addr in jdata['have'].items():
                                if name.startswith('eth0@'):
                                    timebase._timestamp(f"Using {address[0]} for {name}")
                                    net_clients[name] = address[0]
                                else:
                                    net_clients[name] = addr
                    except Exception as exc:
                        timebase._timestamp(f"Failed to parse JSON data: {exc}")
                        continue
                else:
                    ignore, ts, ignore = payload.split()
                ts_clients.append([client,
                                   {
                                    "client_ts": ts,
                                    "request_time": ytime(),
                                    "start_time": start_time,
                                    "base_start_time": base_start_time
                                    }])
            else:
                fail_hard(f"Unexpected request for time sync from {payload}")
        elif command == 'rslt':
            handle_result(tmp_sync_file_base, expected_clients, payload)
        elif command == 'fail':
            timebase._timestamp(f"Detected failure from {address}")
            fail_hard(payload)
        elif command == 'sync':
            if step_interval > 0:
                timebase._timestamp(f"Waiting for {step_interval} seconds...")
                time.sleep(step_interval)
                timebase._timestamp("Done waiting")
        else:
            timebase._timestamp(f"Unknown command from {address}: '{command}'")
        expected_clients -= 1
    if ts_clients:
        reply_timestamp(ts_clients)
    if net_clients:
        msg = json.dumps({'have': net_clients})
        command = f'nsrq {msg}'
        timebase._send_message('127.0.0.1', ns_port, f"{sync_nonce} {command}")
    timebase._timestamp("Sync complete")
    if command == 'rslt':
        return 2
    else:
        return 0


print(sys.argv, file=sys.stderr)
try:
    sync_nonce = sys.argv[1]
    sync_file = sys.argv[2]
    error_file = sys.argv[3]
    controller_timestamp_file = sys.argv[4]
    predelay = float(sys.argv[5])
    postdelay = float(sys.argv[6])
    step_interval = float(sys.argv[7])
    listen_port = int(sys.argv[8])
    ns_port = int(sys.argv[9])
    expected_clients = int(sys.argv[10])
    initial_expected_clients = int(sys.argv[11])
    if initial_expected_clients < 0:
        initial_expected_clients = expected_clients
except Exception as exc:
    timebase._timestamp(f"Can't initialize arguments: {exc}")

start_time = time.time()
base_start_time = start_time
timebase._timestamp("Clusterbuster sync starting")
sock = timebase._get_port(addr=None, port=listen_port)
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
offset_from_controller = controller_timestamp_data['offset_from_controller']

timebase._timestamp("About to adjust timestamp")
timebase._timestamp(f"Max timebase error {offset_from_controller}")
timebase._set_offset(-offset_from_controller)
start_time += offset_from_controller
timebase._timestamp(f"Adjusted timebase by {offset_from_controller} seconds {base_start_time} => {start_time}")
try:
    child = os.fork()
except Exception as exc:
    fatal(f"Fork failed: {exc}")
if child == 0:
    timebase._timestamp("About to launch nameserver")
    nameserver = nameserver(timebase, ns_port, expected_clients).run()
    sys.exit()
else:
    nameserver_pid = child
timebase._timestamp("Starting sync")
first_pass = True
while True:
    if timebase._isfile(tmp_error_file):
        fatal("Job failed, exiting")
    tmp_sync_file = None
    # Ensure that all of the accepted connections get closed by exiting
    # a child process.  This way we don't have to keep track of all of the
    # clients and close them manually.
    try:
        child = os.fork()
    except Exception as exc:
        fatal(f"Fork failed: {exc}")
    status = -1
    if child == 0:
        if first_pass:
            clients = initial_expected_clients
        else:
            clients = expected_clients
        sys.exit(sync_one(sock, tmp_sync_file_base, tmp_error_file, start_time, base_start_time, clients, first_pass))
    else:
        try:
            pid, status = os.wait()
        except Exception as err:
            fatal(f"Wait failed: {err}")
    if first_pass:
        touch("/tmp/clusterbuster-started")
        if predelay > 0:
            timebase._timestamp(f"Waiting {predelay} seconds before start")
            time.sleep(predelay)
        first_pass = False
    if (status >> 8) == 2:
        timebase._timestamp("Final sync complete, finishing up")
        touch("/tmp/clusterbuster-finished")
        break
    elif status & 255:
        fatal(f"Sync killed by signal {status & 255}")
    elif status != 0:
        fatal("Job failed, exiting")

if postdelay > 0:
    timebase._timestamp(f"Waiting {postdelay} seconds before end")
    time.sleep(postdelay)

if timebase._isfile(tmp_error_file):
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
            timebase._timestamp(f"Could not load JSON from {f}: {exc}")
            data.append(dict())
else:
    data = [dict() for i in expected_clients]
result['worker_results'] = data

try:
    with open(tmp_sync_file_base, 'w') as tmp:
        tmp.write(json.dumps(timebase._clean_numbers(result), sort_keys=True, indent=1))
except Exception as exc:
    fatal(f"Can't write to sync file {tmp_sync_file_base}: {exc}")
try:
    os.rename(tmp_sync_file_base, sync_file)
except Exception as exc:
    fatal(f"Can't rename {tmp_sync_file_base} to {sync_file}: {exc}")
timebase._timestamp(f"Waiting for sync file {sync_file} to be removed")
while timebase._isfile(sync_file):
    time.sleep(1)
timebase._timestamp(f"Sync file {sync_file} removed, exiting")
kill_nameserver(timebase)
sys.exit(0)
