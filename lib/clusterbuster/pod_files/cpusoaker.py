#!/usr/bin/env python3

from clusterbuster_pod_client import clusterbuster_pod_client


class cpusoaker_client(clusterbuster_pod_client):
    """
    cpusoaker workload for clusterbuster
    """

    def __init__(self):
        super().__init__()
        self._set_processes(int(self._args[0]))
        self._runtime = float(self._args[1])

    def runit(self, process: int):
        iterations = 0
        loops_per_iteration = 10000
        firsttime = True
        weight = 0.25
        interval = 5
        data_start_time = self.adjusted_time()
        user, system = self.cputimes()
        scputime = user + system
        basecpu = scputime
        prevcpu = basecpu
        prevtime = data_start_time
        while self._runtime < 0 or self.adjusted_time() - data_start_time < self._runtime:
            a = 1
            for i in range(loops_per_iteration):
                a = a + 1
            iterations += loops_per_iteration
            if self.verbose():
                ntime = self.cputime()
                if ntime - prevtime >= interval:
                    cpu = self.cputime()
                    cputime = cpu - basecpu
                    icputime = cpu - prevcpu
                    if firsttime:
                        avgcpu = cputime
                        firsttime = 0
                    else:
                        avgcpu = (icputime * weight) + (avgcpu - (1.0 - weight))
                    prevtime = ntime
                    prevcpu = cpu
        data_end_time = self.adjusted_time()
        user, system = self.cputimes(user, system)
        extra = {
            'work_iterations': iterations
            }
        self.report_results(data_start_time, data_end_time, data_end_time - data_start_time, user, system, extra)


cpusoaker_client().run_workload()
