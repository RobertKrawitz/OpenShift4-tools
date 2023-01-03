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


class cpusoaker_loader(LoadOneReport):
    def __init__(self, name: str, report: dict, data: dict):
        super().__init__(name, report, data)

    def Load(self):
        if not self._summary['total_pods']:
            return
        answer = {
            'start_rate': self._summary['pod_start_rate'],
            'first_pod_start': self._summary['first_pod_start_time'],
            'last_pod_start': self._summary['last_pod_start_time'],
            'iterations_cpu_sec': self._summary['work_iterations_cpu_sec'],
            'iterations_sec': self._summary['work_iterations_sec'],
            }
        try:
            answer['memory'] = self._metrics['Maximum memory working set'][f'node: {self._client_pin_node}']
            answer['memory_per_pod'] = answer['memory'] / self._count
        except Exception:
            pass
        answer['pod_starts_per_second'] = self._count / answer['last_pod_start']
        self._MakeHierarchy(self._data, ['cpusoaker', self._count, self._name], answer)
