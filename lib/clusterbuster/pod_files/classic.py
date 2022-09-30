#!/usr/bin/env python3

import time

from clusterbuster_pod_client import clusterbuster_pod_client


class classic_client(clusterbuster_pod_client):
    """
    Classic test for clusterbuster
    """

    def __init__(self):
        try:
            super().__init__()
            self.sleep_time = float(self._args[0])
            self._set_processes(int(self._args[1]))
        except Exception as err:
            self._abort(f"Init failed! {err} {' '.join(self._args)}")

    def runit(self, process: int):
        self._timestamp("runit")
        data_start_time = self._adjusted_time()
        self._timestamp(f"Got adjusted start time {data_start_time}")
        if self.sleep_time > 0:
            time.sleep(self.sleep_time)
        self._timestamp(f"Slept {self.sleep_time}")
        data_end_time = self._adjusted_time()
        self._timestamp(f"Got adjusted end time {data_start_time}")
        user, sys = self._cputimes()
        self._timestamp(f"User, system CPU time {user} {sys}")
        self._report_results(data_start_time, data_end_time, data_end_time - data_start_time, user, sys)


classic_client().run_workload()
