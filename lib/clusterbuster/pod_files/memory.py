#!/usr/bin/env python3

import time
import signal
from random import randint, seed, random
import resource
import math
import os
import numpy.random

from clusterbuster_pod_client import clusterbuster_pod_client, ClusterBusterPodClientException


class memory_client(clusterbuster_pod_client):
    """
    Memory test for clusterbuster
    """

    def __init__(self):
        try:
            super().__init__()
            self._timestamp(self._args[5])
            self._timestamp(' '.join(self._args))
            self._set_processes(int(self._args[0]))
            self.__runtime = float(self._args[1])
            self.__memory = self.parse_param(self._args[2])
            self.__scan = int(self._args[3])
            self.__stride = int(self._args[4])
            self.__iterations = int(self._args[5])
            self.__idle = self.parse_param(self._args[6])
            self.__random_seed = self._args[7]
            self.__sync_between_iterations = bool(int(self._args[8]))
            self.__iteration_runtime = self.parse_param(self._args[9])
            self.__sleep_first = int(self._args[10])
            self.__run_in_subproc = bool(int(self._args[11]))
            self.__start_probability = None if self._args[12] == '' else float(self._args[12])
            if self.__start_probability is not None and (self.__start_probability < 0 or self.__start_probability > 1):
                raise ClusterBusterPodClientException(f"Start probability must be between 0 and 1 ({self.__start_probability})")
#            if self.__runtime > 0:
#                self.__iterations = int(self.__runtime)
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

    def runone_op(self, start_time: float, iteration: int, size: int, stride: int, runtime: float, scan: int):
        pages = int(size / stride)
        # It's a lot more efficient space-wise to create a small byte array
        # and expand it than to create the entire byte array at once.
        # Creating it all at once temporarily doubles the memory requirement,
        # while expanding it this way does not consume extra memory.
        prealloc_time = self._adjusted_time()
        memory_blk = bytearray(b'a')
        memory_blk *= size
        alloc_time = self._adjusted_time()
        if self.__sync_between_iterations:
            self._sync_to_controller(self._idname([f'postalloc-{iteration}', f' {runtime:.3f} ',
                                                   f' {prealloc_time:.3f} ', f' {alloc_time:.3f} ',
                                                   f' {alloc_time-prealloc_time:.3f} ', self._ts()]))
        run_pages = 0
        loops = 0
        extra_pages = 0
        run_start_time = self._adjusted_time()
        if scan:
            rng = None
            # Per https://stackoverflow.com/questions/2709818/fastest-way-to-generate-1-000-000-random-numbers-in-python
            # this is a much faster way to generate a large number of random numbers (obviously at some
            # memory cost).  Since we're accessing just one word out of each page, we want
            # the random number generation to be fast.
            #
            # On a Ryzen 3900, it's about 10x faster; random.randint() gets about 1.1E+06 random numbers/sec
            # while numpy.random with 1000 integers at a time gets about 1.0E+07 random numbers/sec.
            # Doing more than 1000 yields a small benefit (about 1.1E+07 for 10000 integers),
            # but at a more significant memory cost.
            #
            # Also the time for the rng.integers() call increases as the number of integers per block increases;
            # for 100 it's about 12 usec, for 1000 it's about 25 usec, and for 10000 it's about 150 usec
            # (on an unloaded system).  On a heavily loaded system we can expect that to increase some,
            # possibly enough to affect the loop termination time significantly.
            pageidx = []
            curpageidx = 0
            if scan == 2:
                numbers_per_block = 1000
                rng = numpy.random.default_rng()
                pageidx = rng.integers(pages, high=None, size=numbers_per_block).tolist()
            done = False
            end_time = runtime + time.time()
            while not done:
                for i in range(pages):
                    if scan == 2:
                        if curpageidx >= numbers_per_block:
                            pageidx = rng.integers(pages, high=None, size=numbers_per_block).tolist()
                            curpageidx = 0
                        pp = pageidx[curpageidx]
                        curpageidx += 1
                    else:
                        pp = i
                    char = 32 + (run_pages % 192)
                    if runtime >= 0 and i % 1000 == 0 and time.time() >= end_time:
                        self._timestamp(f"Reached termination at {time.time() - end_time} after {loops} loops and {i} pages")
                        extra_pages = i
                        done = True
                        break
                    memory_blk[pp * stride] = char
                    run_pages += 1
                if not done:
                    self._timestamp(f"Completed loop {loops} offset {end_time - time.time()} from end")
                    loops = loops + 1
        elif runtime >= 0:
            time.sleep(runtime)
        else:
            signal.pause()
        prefree_time = self._adjusted_time()
        if self.__sync_between_iterations:
            self._sync_to_controller(self._idname([f'prefree-{iteration}', f' {prefree_time:.3f} ',
                                                   f' {prefree_time-alloc_time:.3f} ', self._ts()]))
        return [run_pages, prealloc_time, alloc_time, run_start_time, prefree_time, loops, extra_pages]

    def runone_child(self, fd, *args):
        os.write(fd, ' '.join([str(val) for val in self.runone_op(*args)]))

    def runone(self, *args):
        # Ensure that we definitely do free the memory we've used by
        # running the worker in a subprocess.
        start_time = self._adjusted_time()
        run_pages = 0
        if self.__run_in_subproc:
            r, w = os.pipe()
            pid = os.fork()
            if pid == 0:
                try:
                    self.runone_child(w, start_time, *args)
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
                        (run_pages, prealloc_time, alloc_time, run_start_time,
                         prefree_time, loops, extra_pages) = [int(x) for x in os.read(r, 4096).decode().split(' ')]
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
                            raise ClusterBusterPodClientException(f"Child failed, status {int(status / 256)}")
                    except Exception:
                        pass
        else:
            (run_pages, prealloc_time, alloc_time, run_start_time,
             prefree_time, loops, extra_pages) = self.runone_op(start_time, *args)
        return (run_pages, start_time, prealloc_time, alloc_time,
                run_start_time, prefree_time, loops, extra_pages, self._adjusted_time())

    def randval(self, i: list):
        if i[1] == i[0]:
            return i[0]
        else:
            return int(min(i[1], max(i[0], i[0] + (i[2] * randint(0, math.ceil((i[1] - i[0]) / i[2]))))))

    def minval(self, interval: list):
        return interval[0]

    def maxval(self, interval: list):
        return interval[1]

    def avgval(self, interval: list):
        return (interval[0] + interval[1]) / 2

    def runit(self, process: int):
        seed(self._idname(self.__random_seed))
        pages = 0
        elapsed_time = 0
        job_run_time = 0
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
            rand = random()
            # Choice of start probability should not affect
            # the rest of the randomization
            seed(self._idname(self.__random_seed))
            if self.__start_probability is None:
                self.__start_probability = ((self.avgval(self.__iteration_runtime) /
                                             (self.avgval(self.__iteration_runtime) +
                                              self.avgval(self.__idle))))
            if rand > self.__start_probability:
                sleep_time = self.randval(self.__idle)
                self._timestamp(f"Presleeping {sleep_time}")
                time.sleep(sleep_time)
        for iteration in range(self.__iterations):
            self._timestamp(f'Iteration {iteration}/{self.__iterations}')
            if self.__sync_between_iterations:
                self._sync_to_controller(self._idname([f'iteration-{iteration}', self._ts()]))
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
            (run_pages, start_time, prealloc_time, alloc_time,
             run_start_time, prefree_time, loops, extra_pages, end_time) = self.runone(iteration,
                                                                                       run_size, self.__stride,
                                                                                       run_time, self.__scan)
            runs.append({'size': run_size,
                         'runtime': run_time,
                         'start_time': start_time,
                         'prealloc_time': prealloc_time,
                         'alloc_time': alloc_time,
                         'run_start_time': run_start_time,
                         'prefree_time': prefree_time,
                         'end_time': end_time,
                         'elapsed_time': end_time - start_time,
                         'pages': run_pages,
                         'loops': loops,
                         'extra_pages': extra_pages})
            pages += run_pages
            job_run_time += (prefree_time - run_start_time)
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
            'scan': bool(self.__scan),
            'total_pages': pages,
            'iterations': iteration + 1,
            'runtime': job_run_time,
            'rate': pages / job_run_time,
            'cases': runs
            }
        self._report_results(data_start_time, data_end_time, data_end_time - data_start_time,
                             user, system, extras)


memory_client().run_workload()
