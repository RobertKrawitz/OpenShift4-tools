#!/usr/bin/env python3

import time
import random
import math

from clusterbuster_pod_client import clusterbuster_pod_client


class client_client(clusterbuster_pod_client):
    """
    Client/server test for clusterbuster
    """

    def __init__(self):
        try:
            super().__init__()
            self.srvhost = self._resolve_host(self._args[0])
            self.connect_port = int(self._args[1])
            self.data_rate = self._toSize(self._args[2])
            self.nbytes = self._toSize(self._args[3])
            self.bytes_max = self._toSize(self._args[4])
            self.msg_size = self._toSize(self._args[5])
            self.xfertime = self._toSize(self._args[6])
            self.xfertime_max = self._toSize(self._args[7])
        except Exception as err:
            self._abort(f"Init failed! {err} {' '.join(self._args)}")

    def runit(self, process: int):
        npass = 0
        ex = 0
        ex2 = 0

        conn = self._connect_to(self.srvhost, self.connect_port)
        self._sync_to_controller()
        msg = b'A' * self.msg_size

        data_sent = 0
        mean_latency = 0
        max_latency = 0
        stdev_latency = 0

        nbytes = self.nbytes
        xfertime = self.xfertime
        if nbytes != self.bytes_max:
            nbytes += random.randint(0, self.bytes_max - nbytes)
        if xfertime != self.xfertime_max:
            xfertime += random.randint(0, self.xfertime_max - xfertime)

        user, system = self._cputimes()
        data_start_time = self._adjusted_time()
        time_overhead = self._calibrate_time()
        starttime = data_start_time
        while (nbytes > 0 and data_sent < bytes) or (xfertime > 0 and self._adjusted_time() - data_start_time < xfertime):
            rtt_start = self._adjusted_time()
            nleft = self.msg_size
            while nleft > 0:
                nwrite = conn.send(msg[(self.msg_size - nleft):])
                if nwrite > 0:
                    nleft -= nwrite
                    data_sent += nwrite
                else:
                    raise Exception("Unexpected zero length message sent")
            nleft = self.msg_size
            read_failures = 0
            while nleft > 0:
                try:
                    answer = conn.recv(nleft)
                except Exception as error:
                    self._timestamp(f"Read failed: {error}")
                    if read_failures > 2:
                        raise error
                    else:
                        read_failures += 1
                        continue
                nread = len(answer)
                read_failures = 0
                if nread > 0:
                    nleft -= nread
                else:
                    raise Exception("Unexpected zero length msg received")
            en = self._adjusted_time() - rtt_start - time_overhead
            ex += en
            ex2 += en * en
            if en > max_latency:
                max_latency = en
            if self._verbose():
                self._timestamp('Write/Read %d %.6f' % (self.msg_size, en))
            curtime = self._adjusted_time()
            if self.data_rate > 0:
                starttime += self.msg_size / self.data_rate
                if curtime < starttime:
                    if self._verbose():
                        self._timestamp('Sleeping %8.6f', starttime - curtime)
                    time.sleep(starttime - curtime)
                else:
                    if self._verbose():
                        self._timestamp('Not sleeping')
            npass += 1
        data_end_time = self._adjusted_time()
        if npass > 0:
            mean_latency = ex / npass
            if npass > 1:
                stdev_latency = math.sqrt((ex2 - (ex * ex / npass)) / (npass - 1))

        user, system = self._cputimes(user, system)
        elapsed_time = data_end_time - data_start_time
        if elapsed_time <= 0:
            elapsed_time = 0.00000001
        extra = {
            'data_sent_bytes': data_sent,
            'mean_latency_sec': mean_latency,
            'max_latency_sec': max_latency,
            'stdev_latency_sec': stdev_latency,
            'timing_overhead_sec': time_overhead,
            'target_self.data_rate': self.data_rate,
            'passes': npass,
            'self.msg_size': self.msg_size
        }
        self._report_results(data_start_time, data_end_time, data_end_time - data_start_time, user, system, extra)


client_client().run_workload()
