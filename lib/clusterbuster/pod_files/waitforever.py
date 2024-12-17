#!/usr/bin/env python3

import signal
from clusterbuster_pod_client import clusterbuster_pod_client


class waitforever_client(clusterbuster_pod_client):
    """
    Dummy test for clusterbuster; sleep forever.
    """

    def __init__(self):
        try:
            super().__init__()
        except Exception as err:
            self._abort(f"Init failed! {err} {' '.join(self._args)}")

    def runit(self, process: int):
        self._timestamp("Starting waitforever")
        signal.pause()


waitforever_client().run_workload()
