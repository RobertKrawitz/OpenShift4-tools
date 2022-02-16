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
        self._file_operations = ['create', 'remove']
        self._add_timeline_vars(['create.operation_start', 'remove.operation_start'])
        self._add_accumulators(['create.operation_elapsed_time', 'create.user_cpu_time',
                                'create.system_cpu_time', 'create.cpu_time', 'create.operations',
                                'remove.operation_elapsed_time', 'remove.user_cpu_time',
                                'remove.system_cpu_time', 'remove.cpu_time', 'remove.operations'])
        self._set_header_components(['namespace', 'pod', 'container', 'process_id'])

    def __update_report(self, dest: dict, source: dict):
        for op in self._file_operations:
            dest[op.capitalize()] = {}
            dest[op.capitalize()]['Elapsed Time'] = self._fformat(source[op]['operation_elapsed_time'], 3)
            dest[op.capitalize()]['CPU Time'] = self._fformat(source[op]['cpu_time'], 3)
            dest[op.capitalize()]['Operations'] = source[op]['operations']
            dest[op.capitalize()]['Operations/sec'] = self._safe_div(source[op]['operations'],
                                                                     source[op]['operation_elapsed_time'], 0)
            dest[op.capitalize()]['Operations/CPU sec'] = self._safe_div(source[op]['operations'], source[op]['cpu_time'], 0)

    def _generate_summary(self, results: dict):
        # I'd like to do this, but if the nodes are out of sync time-wise, this will not
        # function correctly.
        ClusterBusterReporter._generate_summary(self, results)
        self.__update_report(results, self._summary)

    def _generate_row(self, results: dict, row: dict):
        ClusterBusterReporter._generate_row(self, results, row)
        result = {}
        self.__update_report(result, row)
        results[row['namespace']][row['pod']][row['container']][row['process_id']] = result
