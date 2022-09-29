#!/usr/bin/env python3

import subprocess
from clusterbuster_pod_client import clusterbuster_pod_client


class uperf_server_client(clusterbuster_pod_client):
    """
    Server side of uperf test for clusterbuster
    """

    def __init__(self):
        try:
            super().__init__(initialize_timing_if_needed=False)
            self.listen_port = self._args[0]
        except Exception as err:
            self.abort(f"Init failed! {err} {' '.join(self._args)}")

    def runit(self, process: int):
        self.timestamp(f"Starting uperf server on port {self.listen_port}")
        subprocess.run(['uperf', '-s', '-v', '-P', self.listen_port])
        self.timestamp("Done!")


uperf_server_client().run_workload()
