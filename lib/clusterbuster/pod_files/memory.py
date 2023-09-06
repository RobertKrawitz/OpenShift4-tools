#!/usr/bin/env python3

import time
import signal
import random
import resource

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
            self.__stride = int(self._args[4])
            self.__iterations = int(self._args[5])
            self.__interval = int(self._args[6])
            if not self.__stride or self.__stride <= 0:
                self.__stride = resource.getpagesize()
        except Exception as err:
            self._abort(f"Init failed! {err} {' '.join(self._args)}")

    def runone(self):
        pages = int((self.__memory + self.__stride - 1) / self.__stride)
        # It's a lot more efficient space-wise to create a small byte array
        # and expand it than to create the entire byte array at once.
        # Creating it all at once temporarily doubles the memory requirement,
        # while expanding it this way does not consume extra memory.
        memory_blk = bytearray(b'a')
        memory_blk *= self.__memory
        start_time = self._adjusted_time()
        loops = 0
        if self.__scan:
            while self.__runtime < 0 or self._adjusted_time() - start_time < self.__runtime:
                char = random.randint(32, 255)
                for i in range(pages):
                    memory_blk[i * self.__stride] = char
                loops = loops + 1
        elif self.__runtime >= 0:
            time.sleep(self.__runtime)
        else:
            signal.pause()
        return loops, self._adjusted_time() - start_time

    def runit(self, process: int):
        user, system = self._cputimes()
        loops = 0
        elapsed_time = 0
        data_start_time = self._adjusted_time()
        self._timestamp(f"""
memorysize {self.__memory}
runtime    {self.__runtime}
scan       {self.__scan}
stride     {self.__stride}
interval   {self.__interval}""")

        for loop in range(self.__iterations):
            self._sync_to_controller(self._idname([loop]))
            self._timestamp(f"Iteration {loop}")
            run_loops, run_et = self.runone()
            loops += run_loops
            elapsed_time += elapsed_time
            if loop < self.__iterations - 1:
                time.sleep(self.__interval)
        user, system = self._cputimes(user, system)
        data_end_time = self._adjusted_time()
        extras = {
            'loops': loops,
            'runtime': elapsed_time
            }
        self._report_results(data_start_time, data_end_time, data_end_time - data_start_time,
                             user, system, extras)


memory_client().run_workload()
