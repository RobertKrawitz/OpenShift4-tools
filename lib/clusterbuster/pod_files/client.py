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
            self.srvhost = self._args[0]
            self.connect_port = int(self._args[1])
            self.data_rate = clusterbuster_pod_client.toSize(self._args[2])
            self.nbytes = clusterbuster_pod_client.toSize(self._args[3])
            self.bytes_max = clusterbuster_pod_client.toSize(self._args[4])
            self.msg_size = clusterbuster_pod_client.toSize(self._args[5])
            self.xfertime = clusterbuster_pod_client.toSize(self._args[6])
            self.xfertime_max = clusterbuster_pod_client.toSize(self._args[7])
        except Exception as err:
            self.abort(f"Init failed! {err} {' '.join(self._args)}")

    def runit(self, process: int):
        npass = 0
        ex = 0
        ex2 = 0

        conn = self.connect_to(self.srvhost, self.connect_port)
        msg = ('A' * self.msg_size).encode()

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

        user, system = self.cputimes()
        data_start_time = self.adjusted_time()
        time_overhead = self.calibrate_time()
        starttime = data_start_time
        while (nbytes > 0 and data_sent < bytes) or (xfertime > 0 and self.adjusted_time() - data_start_time < xfertime):
            rtt_start = self.adjusted_time()
            nleft = self.msg_size
            while nleft > 0:
                try:
                    nwrite = conn.send(msg[(self.msg_size - nleft):])
                except Exception as error:
                    self.timestamp(f"Write failed: {error}")
                    return 1
                if nwrite > 0:
                    nleft -= nwrite
                    data_sent += nwrite
                else:
                    self.timestamp("Unexpected zero length msg sent")
                    return 1
            nleft = self.msg_size
            read_failures = 0
            while nleft > 0:
                try:
                    answer = conn.recv(nleft)
                except Exception as error:
                    self.timestamp(f"Read failed: {error}")
                    if read_failures > 2:
                        return 1
                    else:
                        read_failures += 1
                        continue
                nread = len(answer)
                read_failures = 0
                if nread > 0:
                    nleft -= nread
                else:
                    self.timestamp("Unexpected zero length msg received")
                    return 1
            en = self.adjusted_time() - rtt_start - time_overhead
            ex += en
            ex2 += en * en
            if en > max_latency:
                max_latency = en
            if self.verbose():
                self.timestamp('Write/Read %d %.6f' % (self.msg_size, en))
            curtime = self.adjusted_time()
            if self.data_rate > 0:
                starttime += self.msg_size / self.data_rate
                if curtime < starttime:
                    if self.verbose():
                        self.timestamp('Sleeping %8.6f', starttime - curtime)
                    time.sleep(starttime - curtime)
                else:
                    if self.verbose():
                        self.timestamp('Not sleeping')
            npass += 1
        data_end_time = self.adjusted_time()
        if npass > 0:
            mean_latency = ex / npass
            if npass > 1:
                stdev_latency = math.sqrt((ex2 - (ex * ex / npass)) / (npass - 1))

        user, system = self.cputimes(user, system)
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
        self.report_results(data_start_time, data_end_time, data_end_time - data_start_time, user, system, extra)


client_client().run_workload()
