#!/usr/bin/env python3
# Copyright 2022 Robert Krawitz/Red Hat
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

from .ClusterBusterLoader import LoadOneReport
import sys


class fio_loader(LoadOneReport):
    def __init__(self, report: dict, answer: dict):
        LoadOneReport.__init__(self, report, answer)

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
            if 'results' not in self._summary or job not in self._summary['results']:
                print(f'Cannot load fio results for {self._metadata["job_name"]}/{job}', file=sys.stderr)
                continue
            result = self._summary['results'][job]['job_results']
            self._MakeHierarchy(self._answer, ['fio', self._count, ioengine, iodepth, fdatasync,
                                               direct, pattern, blocksize, self._runtime_env, 'total'])
            root = self._answer['fio'][self._count][ioengine][iodepth][fdatasync][direct][pattern][blocksize][self._runtime_env]
            for op, data in result.items():
                if 'data_rate' in result[op]:
                    self._MakeHierarchy(root, [op])
                    root[op]['throughput'] = result[op]['data_rate']
                    if 'throughput' not in root['total']:
                        root['total']['throughput'] = 0
                    root['total']['throughput'] += result[op]['data_rate']
                if 'io_rate' in result[op]:
                    self._MakeHierarchy(root, [op])
                    if 'iops' not in root['total']:
                        root['total']['iops'] = 0
                    root[op]['iops'] = result[op]['io_rate']
                    root['total']['iops'] += result[op]['io_rate']
        print(self._answer, file=sys.stderr)
