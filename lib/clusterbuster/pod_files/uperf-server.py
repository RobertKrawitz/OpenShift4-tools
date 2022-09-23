#!/usr/bin/env python3

import subprocess
from clusterbuster_pod_client import clusterbuster_pod_client


class uperf_server_client(clusterbuster_pod_client):
    """
    Server side of uperf test for clusterbuster
    """

    def __init__(self, **args):
        super().__init__(args)
        self.listen_port = self._args[0]

    def runit(self, process: int):
        self.timestamp("Starting uperf server on port $listen_port")
        subprocess.run(['uperf', '-s', '-v', '-P', self.listen_port])
        self.timestamp("Done!")


uperf_server_client(initialize_timing_if_needed=False).run_workload()
