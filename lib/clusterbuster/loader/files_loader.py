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

from .ClusterBusterLoader import LoadOneReport


class files_loader(LoadOneReport):
    def __init__(self, name: str, report: dict, data: dict):
        super().__init__(name, report, data)

    def Load(self):
        if 'workload_metadata' in self._metadata and 'dirs_per_volume' in self._metadata['workload_metadata']:
            job_metadata = self._metadata['workload_metadata']
        else:
            job_metadata = self._metadata['options']['workloadOptions']
        dirs = job_metadata['dirs_per_volume']
        files = job_metadata['files_per_dir']
        blocksize = job_metadata['file_block_size']
        blocks = job_metadata['file_size']
        direct = job_metadata['files_direct']
        answer = {}
        for op in ['create', 'read', 'remove']:
            self._MakeHierarchy(answer, [op])
            answer[op]['elapsed_time'] = self._summary[op]['operation_elapsed_time']
            answer[op]['cpu_time'] = self._summary[op]['cpu_time']
            answer[op]['cpu_utilization'] = answer[op]['cpu_time'] / answer[op]['elapsed_time']
        answer['read']['io_throughput'] = self._summary['read']['data_rate']
        self._MakeHierarchy(self._data, ['files', self._count, dirs, files, blocksize, blocks, direct, self._name], answer)
