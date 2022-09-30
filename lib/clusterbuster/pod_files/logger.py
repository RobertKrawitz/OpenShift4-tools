#!/usr/bin/env python3

import sys
import time
from clusterbuster_pod_client import clusterbuster_pod_client


class logger_client(clusterbuster_pod_client):
    """
    Logger test for clusterbuster
    """

    def __init__(self):
        try:
            super().__init__()
            self._set_processes(int(self._args[0]))
            self.__xfer_time = float(self._args[1])
            self.__bytes_per_line = clusterbuster_pod_client._toSize(self._args[2])
            self.__lines_per_io = clusterbuster_pod_client._toSize(self._args[3])
            self.__xfer_count = clusterbuster_pod_client._toSize(self._args[4])
            self.__delay = float(self._args[5])
        except Exception as err:
            self._abort(f"Init failed! {err} {' '.join(self._args)}")

    def runit(self, process: int):
        xferbuf = f"{'A' * (self.__bytes_per_line - 1)}\n" * self.__lines_per_io
        user, system = self._cputimes()
        data_start_time = self._adjusted_time()
        xfers = 0
        bytes_transferred = 0
        while ((self.__xfer_time == 0 and self.__xfer_count == 0) or
               (self.__xfer_time > 0 and self._adjusted_time(data_start_time) < self.__xfer_time) or
               (self.__xfer_count > 0 and xfers < self.__xfer_count)):
            self._timestamp('')
            print(xferbuf, file=sys.stderr)
            if self.__delay > 0:
                time.sleep(self.__delay)
            xfers = xfers + 1
            bytes_transferred += len(xferbuf)

        user, system = self._cputimes(user, system)
        data_end_time = self._adjusted_time()
        extras = {
            'bytes_transferred': bytes_transferred
            }
        self._report_results(data_start_time, data_end_time, data_end_time - data_start_time, user, system, extras)


logger_client().run_workload()
