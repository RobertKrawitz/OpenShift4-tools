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
            self.__memory = self.parse_param(self._args[1])
            self.__runtime = self.parse_param(self._args[2])
            self.__scan = bool(int(self._args[3]))
            self.__stride = int(self._args[4])
            self.__iterations = int(self._args[5])
            self.__interval = self.parse_param(self._args[6])
            self.__random_seed = self._args[7]
            if not self.__stride or self.__stride <= 0:
                self.__stride = resource.getpagesize()
        except Exception as err:
            self._abort(f"Init failed! {err} {' '.join(self._args)}")

    def parse_param(self, param: str):
        answer = [int(a) for a in param.split(',', 2)]
        if len(answer) == 1:
            answer.append(answer[0])
        return answer

    def runone(self, size: int, stride: int, runtime: int, scan: bool):
        pages = size / stride
        self._timestamp(f"Running size {size} stride {stride} runtime {runtime} scan {scan}")
        # It's a lot more efficient space-wise to create a small byte array
        # and expand it than to create the entire byte array at once.
        # Creating it all at once temporarily doubles the memory requirement,
        # while expanding it this way does not consume extra memory.
        memory_blk = bytearray(b'a')
        memory_blk *= size
        start_time = self._adjusted_time()
        loops = 0
        if scan:
            while runtime < 0 or self._adjusted_time() - start_time < runtime:
                char = 32 + (loops % 192)
                for i in range(pages):
                    memory_blk[i * stride] = char
                loops = loops + 1
        elif runtime >= 0:
            time.sleep(runtime)
        else:
            signal.pause()
        return loops * pages, start_time, self._adjusted_time() - start_time

    def randval(self, interval: list):
        return random.randint(interval[0], interval[1])

    def runit(self, process: int):
        random.seed(self._idname(self.__random_seed))
        loops = 0
        elapsed_time = 0
        user, system = self._cputimes()
        data_start_time = self._adjusted_time()
        runs = []

        for loop in range(self.__iterations):
            self._sync_to_controller(self._idname([loop]))
            self._timestamp(f"Iteration {loop}")
            run_size = self.randval(self.__memory)
            run_size = self.__stride * int((run_size + self.__stride - 1) / self.__stride)
            run_time = self.randval(self.__runtime)
            run_loops, start_time, run_et = self.runone(run_size, self.__stride,
                                                        run_time, self.__scan)
            runs.append({'size': run_size,
                         'runtime': run_time,
                         'start_time': start_time,
                         'elapsed_time': run_et,
                         'iterations': run_loops})
            loops += run_loops
            elapsed_time += elapsed_time
            if loop < self.__iterations - 1:
                time.sleep(self.randval(self.__interval))
        user, system = self._cputimes(user, system)
        data_end_time = self._adjusted_time()
        extras = {
            'scan': self.__scan,
            'loops': loops,
            'runtime': elapsed_time,
            'cases': runs
            }
        self._report_results(data_start_time, data_end_time, data_end_time - data_start_time,
                             user, system, extras)


memory_client().run_workload()
