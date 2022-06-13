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

from lib.clusterbuster.analysis.ClusterBusterAnalysis import ClusterBusterAnalysis


class cpusoaker_analysis(ClusterBusterAnalysis):
    """
    Analysis cpusoaker data
    """

    def __init__(self, report: dict, answer: dict):
        pass

    def Load(self):
        self._MakeHierarchy(self._answer, ['scaling', self._count, self._runtime_env])
        root = self._answer['scaling'][self._count][self._runtime_env]
        root['start_rate'] = self._summary['pod_start_rate']
        root['first_pod_start'] = self._summary['first_pod_start_time']
        root['last_pod_start'] = self._summary['last_pod_start_time']
        root['iterations_cpu_sec'] = self._summary['work_iterations_cpu_sec']
        root['iterations_sec'] = self._summary['work_iterations_sec']
        root['memory'] = self._metrics['Maximum memory working set'][f'node: {self._client_pin_node}']
        root['memory_per_pod'] = root['memory'] / self._count
        root['pod_starts_per_second'] = self._count / root['last_pod_start']
