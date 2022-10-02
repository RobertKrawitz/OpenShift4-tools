#!/usr/bin/env python3

import os

from clusterbuster_pod_client import clusterbuster_pod_client


class server_client(clusterbuster_pod_client):
    """
    Server class for clusterbuster
    """

    def __init__(self):
        try:
            super().__init__(initialize_timing_if_needed=False)
            self.listen_port = int(self._args[0])
            self.msg_size = clusterbuster_pod_client._toSize(self._args[1])
            self.expected_clients = int(self._args[2])
            self.buf = ('A' * self.msg_size).encode()
        except Exception as err:
            self._abort(f"Init failed! {err} {' '.join(self._args)}")

    def run_one_server(self, conn):
        consec_empty = 0
        ntotal = 0
        while True:
            while ntotal < self.msg_size:
                try:
                    answer = conn.recv(self.msg_size - ntotal)
                except Exception as err:
                    self._timestamp(f"Recv failed: {err}")
                    os._exit(1)
                if len(answer) == 0:
                    if consec_empty > 1:
                        self._timestamp(f"Exiting {conn}")
                    os._exit(0)
                    consec_empty = consec_empty + 1
                else:
                    consec_empty = 0
                    ntotal += len(answer)
            while ntotal > 0:
                try:
                    answer = conn.send(self.buf[(self.msg_size - ntotal):])
                except Exception as err:
                    self._timestamp(f"Send failed: {err}")
                    os._exit(1)
                ntotal -= answer

    def runit(self, process: int):
        expected_clients = self.expected_clients
        sock = self._listen(None, port=self.listen_port, backlog=self.expected_clients)

        pid_count = 0
        while expected_clients > 0:
            try:
                conn, address = sock.accept()
            except Exception as err:
                self._timestamp(f"Accept failed: {err}")
                return 1
            try:
                child = os.fork()
                if child == 0:
                    sock.close()
                    self._timestamp(f"Accepted connection from {address}")
                    self.run_one_server(conn)
                else:
                    conn.close()
                    pid_count += 1
                    expected_clients -= 1
            except Exception as err:
                self._timestamp(f"Fork failed: {err}")
        self._timestamp("Waiting for all clients to exit:")
        while pid_count > 0:
            try:
                pid, status = os.wait()
                self._timestamp(f"waited for {pid} => {status}")
                if status != 0:
                    status = int((status / 256)) | (status & 255)
                    return(1)
                pid_count = pid_count - 1
            except Exception as err:
                self._timestamp(f'Wait failed: {err}')
                return(1)
        return 0


server_client().run_workload()
