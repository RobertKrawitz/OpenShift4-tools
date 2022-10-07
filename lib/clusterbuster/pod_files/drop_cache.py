#!/usr/bin/env python3

import os
from clusterbuster_pod_client import clusterbuster_pod_client


class drop_cache_client(clusterbuster_pod_client):
    """
    Drop buffer cache and if needed host cache
    """
    def __init__(self):
        try:
            super().__init__(initialize_timing_if_needed=False)
            self.listen_port = int(self._args[0])
        except Exception as err:
            self._abort(f"Init failed! {err} {' '.join(self._args)}")

    def runit(self, process: int):
        sock = self._listen(port=self.listen_port, backlog=128)
        while True:
            try:
                conn, address = sock.accept()
                self._timestamp(f"Accepted connection from {address}, about to sync()")
                os.sync()
                self._timestamp("About to drop cache")
                try:
                    with open("/proc/sys/vm/drop_caches", 'w') as drop_cache:
                        print('3', file=drop_cache)
                    self._timestamp("Successfully dropped cache")
                except Exception as exc:
                    self._timestamp(f"Cannot write to /proc/sys/vm/drop_caches: {exc}")
                conn.close()
            except Exception:
                pass


drop_cache_client().run_workload()
