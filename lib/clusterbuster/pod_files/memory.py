#!/usr/bin/env python3

import time
import signal
import random
import resource
import math
import os

from clusterbuster_pod_client import clusterbuster_pod_client


class memory_client(clusterbuster_pod_client):
    """
    Memory test for clusterbuster
    """

    def __init__(self):
        try:
            super().__init__()
            self._set_processes(int(self._args[0]))
            self.__runtime = float(self._args[1])
            self.__memory = self.parse_param(self._args[2])
            self.__scan = bool(int(self._args[3]))
            self.__stride = int(self._args[4])
            self.__iterations = int(self._args[5])
            self.__idle = self.parse_param(self._args[6])
            self.__random_seed = self._args[7]
            self.__sync_between_iterations = bool(int(self._args[8]))
            self.__iteration_runtime = self.parse_param(self._args[9])
            self.__sleep_first = int(self._args[10])
            if self.__runtime > 0:
                self.__iterations = int(self.__runtime)
            if not self.__stride or self.__stride <= 0:
                self.__stride = resource.getpagesize()
        except Exception as err:
            self._abort(f"Init failed! {err} {' '.join(self._args)}")

    def parse_param(self, param: str):
        answer = [int(a) for a in param.split(',', 3)]
        if len(answer) == 1:
            answer.append(answer[0])
        if len(answer) == 2:
            answer.append(1)
        if answer[1] < answer[0]:
            answer[1] = answer[0]
        answer[2] = max(1, min(answer[2], answer[1] - answer[0]))
        return answer

    def runone_child(self, fd, start_time: float, size: int, stride: int, runtime: float, scan: bool):
        pages = int(size / stride)
        # It's a lot more efficient space-wise to create a small byte array
        # and expand it than to create the entire byte array at once.
        # Creating it all at once temporarily doubles the memory requirement,
        # while expanding it this way does not consume extra memory.
        memory_blk = bytearray(b'a')
        memory_blk *= size
        loops = 0
        if scan:
            while runtime < 0 or self._adjusted_time() - start_time < runtime:
                char = 32 + (loops % 192)
                for i in range(pages):
                    memory_blk[i * stride] = char
                loops += 1
        elif runtime >= 0:
            time.sleep(runtime)
        else:
            signal.pause()
        os.write(fd, str(loops * stride).encode())

    def runone(self, size: int, stride: int, runtime: float, scan: bool):
        # Ensure that we definitely do free the memory we've used by
        # running the worker in a subprocess.
        r = None
        w = None
        start_time = self._adjusted_time()
        loops = 0
        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:
            try:
                self.runone_child(w, start_time, size, stride, runtime, scan)
            except Exception as exc:
                self._timestamp(f"Run child failed: {exc}")
                os._exit(1)
            os._exit(0)
        else:
            try:
                try:
                    w.close()
                except Exception:
                    pass
                try:
                    loops = int(os.read(r, 4096).decode())
                except Exception as e:
                    self._timestamp(f"Read failed: {e}")
            finally:
                try:
                    r.close()
                except Exception:
                    pass
                try:
                    cpid, status = os.waitpid(pid)
                    if status:
                        raise Exception(f"Child failed, status {int(status / 256)}")
                except Exception:
                    pass
            return loops, start_time, self._adjusted_time() - start_time

    def randval(self, interval: list):
        if interval[1] == interval[0]:
            return interval[0]
        return int(min(interval[1], max(interval[0], interval[0] + (interval[2] * random.randint(0, math.ceil((interval[1] - interval[0]) / interval[2]))))))

    def minval(self, interval: list):
        return interval[0]

    def maxval(self, interval: list):
        return interval[1]

    def avgval(self, interval: list):
        return (interval[0] + interval[1]) / 2

    def runit(self, process: int):
        random.seed(self._idname(self.__random_seed))
        pages = 0
        elapsed_time = 0
        user, system = self._cputimes()
        data_start_time = self._adjusted_time()
        if self.__runtime > 0:
            desired_end_time = self.__runtime + data_start_time
        else:
            desired_end_time = 0
        runs = []

        max_sleep = self.maxval(self.__idle)
        if self.__sleep_first == 1:
            sleep_time = self.randval(self.__idle)
            self._timestamp(f"Presleeping {sleep_time}")
            time.sleep(sleep_time)
        elif self.__sleep_first > 1:
            prob = random.random()
            random.seed(self._idname(self.__random_seed))
            if prob > ((self.avgval(self.__iteration_runtime) /
                        (self.avgval(self.__iteration_runtime) + self.avgval(self.__idle)))):
                sleep_time = self.randval(self.__idle)
                self._timestamp(f"Presleeping {sleep_time}")
                time.sleep(sleep_time)
        for iteration in range(self.__iterations):
            if self.__sync_between_iterations:
                self._sync_to_controller(self._idname([iteration]))
            run_size = self.randval(self.__memory)
            run_size = self.__stride * int((run_size + self.__stride - 1) / self.__stride)
            run_time = self.randval(self.__iteration_runtime)
            curtime = self._adjusted_time()
            if desired_end_time > 0:
                if curtime >= desired_end_time:
                    iteration = iteration - 1
                    break
                elif run_time > desired_end_time - curtime - (max_sleep if self.__sleep_first == 0 else 0):
                    run_time = desired_end_time - curtime
            self._timestamp(f"Running size {run_size} stride {self.__stride} runtime {run_time} scan {self.__scan}")
            run_pages, start_time, run_et = self.runone(run_size, self.__stride,
                                                        run_time, self.__scan)
            runs.append({'size': run_size,
                         'runtime': run_time,
                         'start_time': start_time,
                         'end_time': run_et + start_time,
                         'elapsed_time': run_et,
                         'pages': run_pages})
            pages += run_pages
            elapsed_time += elapsed_time
            curtime = self._adjusted_time()
            sleep_time = self.randval(self.__idle)
            if desired_end_time > 0 and sleep_time > desired_end_time - curtime:
                break
            if iteration < self.__iterations - 1:
                self._timestamp(f"Sleeping {sleep_time}")
                time.sleep(sleep_time)
        user, system = self._cputimes(user, system)
        data_end_time = self._adjusted_time()
        extras = {
            'scan': self.__scan,
            'total_pages': pages,
            'iterations': iteration + 1,
            'runtime': data_end_time - data_start_time,
            'rate': pages / (data_end_time - data_start_time),
            'cases': runs
            }
        self._report_results(data_start_time, data_end_time, data_end_time - data_start_time,
                             user, system, extras)


memory_client().run_workload()
