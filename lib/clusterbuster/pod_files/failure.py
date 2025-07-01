#!/usr/bin/env python3

import time

from clusterbuster_pod_client import clusterbuster_pod_client, ClusterBusterPodClientException


class failure_client(clusterbuster_pod_client):
    """
    Failure test for clusterbuster
    """

    def __init__(self):
        try:
            super().__init__()
            self._set_processes(int(self._args[0]))
            self.__delaytime = int(self._args[1])
        except Exception as err:
            self._abort(f"Init failed! {err} {' '.join(self._args)}")

    def runit(self, process: int):
        time.sleep(self.__delaytime)

        self._timestamp(f'About to fail after {self.__delaytime} seconds!')
        raise ClusterBusterPodClientException(f'Failing as intended after {self.__delaytime} seconds')


failure_client().run_workload()
