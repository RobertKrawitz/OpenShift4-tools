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

from lib.clusterbuster.reporter.ClusterBusterReporter import ClusterBusterReporter


class cpusoaker_reporter(ClusterBusterReporter):
    def __init__(self, jdata: dict, report_format: str):
        ClusterBusterReporter.__init__(self, jdata, report_format)
        self._add_accumulators(['work_iterations'])
        self._set_header_components(['namespace', 'pod', 'container', 'process_id'])

    def _generate_summary(self, results: dict):
        # I'd like to do this, but if the nodes are out of sync time-wise, this will not
        # function correctly.
        ClusterBusterReporter._generate_summary(self, results)
        results['Interations'] = self._summary['work_iterations']
        results['Iterations/sec'] = self._safe_div(self._summary['work_iterations'], self._summary['data_run_interval'], 0)
        results['Interations/CPU sec'] = self._safe_div(self._summary['work_iterations'], self._summary['cpu_time'], 0)

    def _generate_row(self, results: dict, row: dict):
        ClusterBusterReporter._generate_row(self, results, row)
        result = {}
        result['Elapsed Time'] = self._fformat(row['data_elapsed_time'], 3)
        result['Iterations'] = row['work_iterations']
        result['Iterations/sec'] = self._safe_div(row['work_iterations'], row['data_elapsed_time'], 0)
        result['Iterations/CPU sec'] = self._safe_div(row['work_iterations'], row['cpu_time'], 0)
        self._insert_into(results, [row['namespace'], row['pod'], row['container']], result)
