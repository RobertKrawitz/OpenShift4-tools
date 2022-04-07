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

import re
from lib.clusterbuster.reporter.ClusterBusterReporter import ClusterBusterReporter


class sysbench_reporter(ClusterBusterReporter):
    def __init__(self, jdata: dict, report_format: str):
        ClusterBusterReporter.__init__(self, jdata, report_format)
        self._sysbench_operations = jdata['metadata']['options']['workloadOptions']['sysbench_fileio_tests']
        self._sysbench_vars_to_copy = ['filesize:precision=3:suffix=B:base=1024',
                                       'blocksize:precision=3:suffix=B:base=1024', 'rdwr_ratio',
                                       'fsync_frequency', 'final_fsync_enabled', 'io_mode']
        accumulators = []
        vars_to_copy = []
        for op in self._sysbench_operations:
            workload = f'workloads.{op}'
            for var in ['elapsed_time', 'user_cpu_time', 'sys_cpu_time',
                        'read_ops', 'write_ops', 'fsync_ops',
                        'mean_latency_sec', 'max_latency_sec', 'p95_latency_sec', 'files']:
                accumulators.append(f'{workload}.{var}')
            for var in self._sysbench_vars_to_copy:
                vars_to_copy.append(f'{workload}.{re.sub(r":.*", "", var)}')
        self._add_accumulators(accumulators)
        self._add_fields_to_copy(vars_to_copy)
        self._set_header_components(['namespace', 'pod', 'container', 'process_id'])

    def __update_report(self, dest: dict, source: dict, sample_row: dict = None):
        if sample_row is None:
            sample_row = source
        for op in self._sysbench_operations:
            pop = f'workload: {op}'
            dest[pop] = {}
            dest[pop]['Elapsed Time'] = self._fformat(source[op]['elapsed_time'], 3)
            dest[pop]['CPU Time'] = self._fformat(source[op]['user_cpu_time'] + source[op]['sys_cpu_time'], 3)
            for var in ['read_ops:precision=3:suffix=ops:base=1000:integer=1',
                        'write_ops:precision=3:suffix=ops:base=1000:integer=1',
                        'fsync_ops:precision=3:suffix=ops:base=1000:integer=1',
                        'files:precision=3:suffix='':base=1000:integer=1']:
                self._copy_formatted_value(var, dest[pop], source[op])
            for var in self._sysbench_vars_to_copy:
                self._copy_formatted_value(var, dest[pop], source[op])
            dest[pop]['read ops rate'] = self._prettyprint(self._safe_div(source[op]['read_ops'], source[op]['elapsed_time']),
                                                           precision=3, base=1000, suffix='ops/sec')
            dest[pop]['write ops rate'] = self._prettyprint(self._safe_div(source[op]['write_ops'], source[op]['elapsed_time']),
                                                            precision=3, base=1000, suffix='ops/sec')
            dest[pop]['read data rate'] = self._prettyprint(self._safe_div(source[op]['blocksize'] * source[op]['read_ops'],
                                                                           source[op]['elapsed_time']),
                                                            precision=3, base=1024, suffix='B/sec')
            dest[pop]['write MiB/sec'] = self._prettyprint(self._safe_div(source[op]['blocksize'] * source[op]['write_ops'],
                                                                          source[op]['elapsed_time']),
                                                           precision=3, base=1024, suffix='B/sec')

    def _generate_summary(self, results: dict):
        # I'd like to do this, but if the nodes are out of sync time-wise, this will not
        # function correctly.
        ClusterBusterReporter._generate_summary(self, results)
        sample_row = self._jdata['Results']['worker_results'][0]['workloads']
        self.__update_report(results, self._summary['workloads'], sample_row)

    def _generate_row(self, results: dict, row: dict):
        ClusterBusterReporter._generate_row(self, results, row)
        result = {}
        self.__update_report(result, row['workloads'])
        self._insert_into(results, [row['namespace'], row['pod'], row['container'], str(row['process_id'])], result)
