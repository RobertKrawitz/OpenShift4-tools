#!/usr/bin/env python3

import os

from clusterbuster_pod_client import clusterbuster_pod_client


class server_client(clusterbuster_pod_client):
    """
    Server class for clusterbuster
    """

    def __init__(self):
        try:
            super().__init__()
            self.listen_port = int(self._args[0])
            self.msg_size = self._toSize(self._args[1])
            self.expected_clients = int(self._args[2])
            self.buf = b'B' * self.msg_size
        except Exception as err:
            self._abort(f"Init failed! {err} {' '.join(self._args)}")

    def run_one_server(self, conn):
        consec_empty = 0
        ntotal = 0
        while True:
            while ntotal < self.msg_size:
                answer = conn.recv(self.msg_size - ntotal)
                if len(answer) == 0:
                    if consec_empty > 1:
                        self._timestamp(f"Exiting {conn}")
                    return
                    consec_empty = consec_empty + 1
                else:
                    consec_empty = 0
                    ntotal += len(answer)
            while ntotal > 0:
                answer = conn.send(self.buf[(self.msg_size - ntotal):])
                ntotal -= answer

    def runit(self, process: int):
        expected_clients = self.expected_clients
        sock = self._listen(port=self.listen_port, backlog=self.expected_clients)

        pid_count = 0
        while expected_clients > 0:
            conn, address = sock.accept()
            child = os.fork()
            if child == 0:
                sock.close()
                self._timestamp(f"Accepted connection from {address}")
                self.run_one_server(conn)
                return
            else:
                conn.close()
                pid_count += 1
                expected_clients -= 1
        self._timestamp("Waiting for all clients to exit:")
        while pid_count > 0:
            pid, status = os.wait()
            self._timestamp(f"waited for {pid} => {status}")
            if status != 0:
                status = int((status / 256)) | (status & 255)
                return 1
            pid_count = pid_count - 1


server_client().run_workload()
