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


class files_reporter(ClusterBusterReporter):
    def __init__(self, jdata: dict, report_format: str):
        ClusterBusterReporter.__init__(self, jdata, report_format)
        self._file_operations = ['create', 'read', 'remove']
        self._add_timeline_vars(['create.operation', 'read.operation', 'remove.operation'])
        self._add_accumulators(['create.user_cpu_time', 'create.system_cpu_time', 'create.cpu_time', 'create.operations',
                                'read.user_cpu_time', 'read.system_cpu_time', 'read.cpu_time', 'read.operations', 'read.total_files', 'read.data_size', 'read.data_rate',
                                'remove.user_cpu_time', 'remove.system_cpu_time', 'remove.cpu_time', 'remove.operations',
                                'summary.total_dirs', 'summary.total_files', 'summary.data_size'])
        self._set_header_components(['namespace', 'pod', 'container', 'process_id'])

    def __update_report(self, dest: dict, source: dict):
        for op in self._file_operations:
            cop = op.capitalize()
            sop = source[op]
            dest[cop] = {}
            dest[cop]['Elapsed Time'] = self._fformat(sop['operation_elapsed_time'], 3)
            dest[cop]['CPU Time'] = self._fformat(sop['cpu_time'], 3)
            dest[cop]['Operations'] = sop['operations']
            dest[cop]['Operations/sec'] = self._safe_div(sop['operations'], sop['operation_elapsed_time'], 0)
            dest[cop]['Operations/CPU sec'] = self._safe_div(sop['operations'], sop['cpu_time'], 0)
            if op == 'read':
                dest[cop]['Total Files'] = sop['total_files']
                dest[cop]['Total Data'] = sop['data_size']
                dest[cop]['IO Throughput'] = sop['data_rate']

    def _generate_summary(self, results: dict):
        # I'd like to do this, but if the nodes are out of sync time-wise, this will not
        # function correctly.
        ClusterBusterReporter._generate_summary(self, results)
        self.__update_report(results, self._summary)
        results['Total Files'] = self._summary['summary']['total_files']
        results['Total Dirs'] = self._summary['summary']['total_dirs']
        results['Total Data'] = self._summary['summary']['data_size']

    def _generate_row(self, results: dict, row: dict):
        ClusterBusterReporter._generate_row(self, results, row)
        result = {}
        self.__update_report(result, row)
        self._insert_into(results, [row['namespace'], row['pod'], row['container'], row['process_id']], result)
