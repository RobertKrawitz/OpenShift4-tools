#!/usr/bin/env python3

import time
import signal
import string
import random

from clusterbuster_pod_client import clusterbuster_pod_client


class memory_client(clusterbuster_pod_client):
    """
    Memory test for clusterbuster
    """

    def __init__(self):
        try:
            super().__init__()
            self._set_processes(int(self._args[0]))
            self.__memory = int(self._args[1])
            self.__runtime = int(self._args[2])
            self.__scan = bool(int(self._args[3]))
        except Exception as err:
            self._abort(f"Init failed! {err} {' '.join(self._args)}")

    def runit(self, process: int):
        user, system = self._cputimes()
        data_start_time = self._adjusted_time()
        memory_blk = bytearray(b'a' * self.__memory)  # noqa: F841

        if self.__scan:
            while self.__runtime < 0 or self._adjusted_time() - data_start_time < self.__runtime:
                char = random.randint(32, 255)
                for i in range(0, self.__memory):
                    memory_blk[i] = char
        else:
            if self.__runtime >= 0:
                time.sleep(self.__runtime)
            else:
                signal.pause()

        user, system = self._cputimes(user, system)
        data_end_time = self._adjusted_time()
        self._report_results(data_start_time, data_end_time, data_end_time - data_start_time, user, system)


memory_client().run_workload()
