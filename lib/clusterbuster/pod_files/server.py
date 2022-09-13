#!/usr/bin/env python3

import sys
import os
import socket


if 'BAK_CONFIGMAP' in os.environ:
    sys.path.insert(0, os.environ['BAK_CONFIGMAP'])
from clusterbuster_pod_client import clusterbuster_pod_client

client = clusterbuster_pod_client()
listen_port, msg_size, ts, expected_clients = client.command_line()
listen_port = int(listen_port)
msg_size = int(msg_size)
expected_clients = int(expected_clients)
buf = ('A' * msg_size).encode()


def run_one_server(conn):
    consec_empty = 0
    ntotal = 0
    while True:
        while ntotal < msg_size:
            try:
                answer = conn.recv(msg_size - ntotal)
            except Exception as err:
                client.timestamp(f"Recv failed: {err}")
                os._exit(1)
            if len(answer) == 0:
                if consec_empty > 1:
                    client.timestamp(f"Exiting {conn}")
                os._exit(0)
                consec_empty = consec_empty + 1
            else:
                consec_empty = 0
                ntotal += len(answer)
        while ntotal > 0:
            try:
                answer = conn.send(buf[(msg_size - ntotal):])
            except Exception as err:
                client.timestamp(f"Send failed: {err}")
                os._exit(1)
            ntotal -= answer


def runit():
    global client, expected_clients
    sock = client.listen(port=listen_port, backlog=expected_clients)

    pid_count = 0
    while expected_clients > 0:
        try:
            conn, address = sock.accept()
        except Exception as err:
            client.timestamp(f"Accept failed: {err}")
            return 1
        try:
            child = os.fork()
            if child == 0:
                sock.close()
                client.timestamp(f"Accepted connection from {address}")
                run_one_server(conn)
            else:
                conn.close()
                pid_count += 1
                expected_clients -= 1
        except Exception as err:
            client.timestamp(f"Fork failed: {err}")
    client.timestamp("Waiting for all clients to exit:")
    while pid_count > 0:
        try:
            pid, status = os.wait()
            client.timestamp(f"waited for {pid} => {status}")
            if status != 0:
                status = int((status / 256)) | (status & 255)
                return(1)
            pid_count = pid_count - 1
        except Exception as err:
            client.timestamp(f'Wait failed: {err}')
            return(1)
    return 0


client.run_workload(runit)
