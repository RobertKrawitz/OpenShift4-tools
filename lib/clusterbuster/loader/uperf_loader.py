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


class uperf_loader(LoadOneReport):
    def __init__(self, report: dict, answer: dict):
        LoadOneReport.__init__(self, report, answer)

    def Load(self):
        job_name = sorted(self._metadata['workload_metadata']['jobs'].keys())[0]
        job_metadata = self._metadata['workload_metadata']['jobs'][job_name]
        msgsize = job_metadata['msgsize']
        threads = job_metadata['nthr']
        op = job_metadata['test_type']
        job = self._summary['results'][job_name]['summary']

        self._MakeHierarchy(self._answer, ['uperf', self._count, msgsize, threads, self._runtime_env])
        root = self._answer['uperf'][self._count][msgsize][threads][self._runtime_env]
        root[f'cpu_util_{op}'] = self._metrics['CPU utilization']['Total'][f'instance: {self._client_pin_node}']
        if op == 'stream':
            root['rate'] = job['data_rate']
        elif op == 'rr':
            root['ops_sec'] = job['ops_rate']
            root['avg_time_op'] = job['total']['avg_time_avg']
            root['max_time_op'] = job['total']['max_time_max']
