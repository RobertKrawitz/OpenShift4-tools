#!/usr/bin/env python3

import time
from clusterbuster_pod_client import clusterbuster_pod_client


class synctest_client(clusterbuster_pod_client):
    """
    Sync test test for clusterbuster
    """

    def __init__(self):
        try:
            super().__init__()
            self.sync_count = int(self._args[0])
            self.sync_cluster_count = int(self._args[1])
            self.sync_sleep = float(self._args[2])
            self._set_processes(int(self._args[3]))
        except Exception as err:
            self._abort(f"Init failed! {err} {' '.join(self._args)}")

    def runit(self, process: int):
        user, system = self._cputimes()
        data_start_time = self._adjusted_time()
        for i in range(self.sync_count):
            for j in range(self.sync_cluster_count):
                self._sync_to_controller(self._idname([i, j]))
            if self.sync_sleep > 0:
                time.sleep(self.sync_sleep)
        user, system = self._cputimes(user, system)
        data_end_time = self._adjusted_time()
        self._report_results(data_start_time, data_end_time, data_end_time - data_start_time, user, system)


synctest_client().run_workload()
