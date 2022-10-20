#!/usr/bin/env python3

import subprocess
import time
from clusterbuster_pod_client import clusterbuster_pod_client


class uperf_server_client(clusterbuster_pod_client):
    """
    Server side of uperf test for clusterbuster
    """

    def __init__(self):
        try:
            super().__init__()
            self.listen_port = self._args[0]
        except Exception as err:
            self._abort(f"Init failed! {err} {' '.join(self._args)}")

    def runit(self, process: int):
        self._timestamp(f"Starting uperf server on port {self.listen_port}")
        while subprocess.run(['uperf', '-s', '-v', '-P', self.listen_port]).returncode != 0:
            self._timestamp("uperf server failed to start: retrying in 10 seconds")
            time.sleep(10)
        self._timestamp("Done!")


uperf_server_client().run_workload()
