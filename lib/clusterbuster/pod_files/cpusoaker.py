#!/usr/bin/env python3

from clusterbuster_pod_client import clusterbuster_pod_client


class cpusoaker_client(clusterbuster_pod_client):
    """
    cpusoaker workload for clusterbuster
    """

    def __init__(self):
        try:
            super().__init__()
            self._set_processes(int(self._args[0]))
            self._runtime = float(self._args[1])
        except Exception as err:
            self._abort(f"Init failed! {err} {' '.join(self._args)}")

    def runit(self, process: int):
        iterations = 0
        loops_per_iteration = 10000
        firsttime = True
        weight = 0.25
        interval = 5
        data_start_time = self._adjusted_time()
        user, system = self._cputimes()
        scputime = user + system
        basecpu = scputime
        prevcpu = basecpu
        prevtime = data_start_time
        while self._runtime < 0 or self._adjusted_time() - data_start_time < self._runtime:
            a = 1
            for i in range(loops_per_iteration):
                a = a + 1
            iterations += loops_per_iteration
            if self._verbose():
                ntime = self._cputime()
                if ntime - prevtime >= interval:
                    cpu = self._cputime()
                    cputime = cpu - basecpu
                    icputime = cpu - prevcpu
                    if firsttime:
                        avgcpu = cputime
                        firsttime = 0
                    else:
                        avgcpu = (icputime * weight) + (avgcpu - (1.0 - weight))
                    prevtime = ntime
                    prevcpu = cpu
        data_end_time = self._adjusted_time()
        user, system = self._cputimes(user, system)
        extra = {
            'work_iterations': iterations
            }
        self._report_results(data_start_time, data_end_time, data_end_time - data_start_time, user, system, extra)


cpusoaker_client().run_workload()
