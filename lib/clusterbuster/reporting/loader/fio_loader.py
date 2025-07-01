#!/usr/bin/env python3
# Copyright 2022-2023 Robert Krawitz/Red Hat
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from .ClusterBusterLoader import ClusterBusterLoadOneReportBase
import sys


class fio_loader(ClusterBusterLoadOneReportBase):
    def __init__(self, name: str, report: dict, data: dict, extras=None):
        super().__init__(name, report, data, extras=extras)

    def Load(self):
        jobs = sorted(self._metadata['workload_metadata']['jobs'])
        for job in jobs:
            job_metadata = self._metadata['workload_metadata']['jobs'][job]
            pattern = job_metadata['pattern']
            blocksize = job_metadata['blocksize']
            iodepth = job_metadata['iodepth']
            fdatasync = job_metadata['fdatasync']
            direct = job_metadata['direct']
            ioengine = job_metadata['ioengine']
            numjobs = job_metadata.get('numjobs', 1)
            if 'results' not in self._summary or job not in self._summary['results']:
                print(f'Cannot load fio results for {self._metadata["job_name"]}/{job}', file=sys.stderr)
                continue
            result = self._summary['results'][job]['job_results']
            self._MakeHierarchy(self._data, ['fio', self._count, ioengine, iodepth, numjobs, fdatasync,
                                             direct, pattern, blocksize, self._name, 'total'])
            root = self._data['fio'][self._count][ioengine][iodepth][numjobs][fdatasync][direct][pattern][blocksize][self._name]
            lat_counter = 0
            for op, data in result.items():
                if 'data_rate' in result[op]:
                    self._MakeHierarchy(root, [op, 'throughput'], result[op]['data_rate'])
                    if 'throughput' not in root['total']:
                        root['total']['throughput'] = 0
                    root['total']['throughput'] += result[op]['data_rate']
                if 'io_rate' in result[op]:
                    self._MakeHierarchy(root, [op, 'iops'], result[op]['io_rate'])
                    if 'iops' not in root['total']:
                        root['total']['iops'] = 0
                    root['total']['iops'] += result[op]['io_rate']
                if 'lat_ns' in result[op]:
                    lat_counter = lat_counter + 1
                    self._MakeHierarchy(root, [op, 'latency_avg'], result[op]['lat_ns']['mean'])
                    self._MakeHierarchy(root, [op, 'latency_max'], result[op]['lat_ns']['max'])
                    if 'latency_avg' not in root['total']:
                        root['total']['latency_avg'] = 0
                        root['total']['latency_max'] = 0
                    root['total']['latency_avg'] += result[op]['lat_ns']['mean']
                    if result[op]['lat_ns']['max'] > root['total']['latency_avg']:
                        root['total']['latency_max'] = result[op]['lat_ns']['max']
            if lat_counter > 0:
                root['total']['latency_avg'] /= lat_counter
