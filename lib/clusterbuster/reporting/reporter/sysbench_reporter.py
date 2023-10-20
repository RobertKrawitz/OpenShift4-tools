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

import re
from .ClusterBusterReporter import ClusterBusterReporter


class sysbench_reporter(ClusterBusterReporter):
    def __init__(self, jdata: dict, report_format: str, extras=None):
        super().__init__(jdata, report_format, extras)
        self._set_header_components(['namespace', 'pod', 'container', 'process_id'])
        self._is_fileio = 'sysbench_fileio_tests' in jdata['metadata']['options']['workloadOptions']
        if self._is_fileio:
            self.__initialize_fileio(jdata)
        else:
            self.__initialize_simple(jdata)

    def __initialize_fileio(self, jdata):
        if 'sysbench_fileio_modes' in jdata['metadata']['options']['workloadOptions']:
            self._sysbench_operations = [f'fileio+{test}+{mode}'
                                         for test in jdata['metadata']['options']['workloadOptions']['sysbench_fileio_tests']
                                         for mode in jdata['metadata']['options']['workloadOptions']['sysbench_fileio_modes']]
        else:
            self._sysbench_operations = jdata['metadata']['options']['workloadOptions']['sysbench_fileio_tests']
        self._sysbench_vars_to_copy = ['filesize:precision=3:suffix=B:base=1024',
                                       'blocksize:precision=3:suffix=B:base=1024', 'rdwr_ratio',
                                       'fsync_frequency', 'final_fsync_enabled', 'io_mode']
        accumulators = []
        vars_to_copy = []
        timeline_vars = []
        for op in self._sysbench_operations:
            workload = f'workloads.{op}'
            for var in ['elapsed_time', 'user_cpu_time', 'sys_cpu_time',
                        'read_ops', 'write_ops', 'fsync_ops',
                        'mean_latency_sec', 'max_latency_sec', 'p95_latency_sec', 'files']:
                accumulators.append(f'{workload}.{var}')
            timeline_vars.append(f'{workload}.op')
            for var in self._sysbench_vars_to_copy:
                vars_to_copy.append(f'{workload}.{re.sub(r":.*", "", var)}')
        self._add_accumulators(accumulators)
        self._add_fields_to_copy(vars_to_copy)
        self._add_timeline_vars(timeline_vars)

    def __initialize_simple(self, jdata):
        self._sysbench_operations = jdata['Results']['worker_results'][0]['workloads'].keys()
        self._sysbench_vars_to_copy = ['threads']
        accumulators = []
        vars_to_copy = []
        for op in self._sysbench_operations:
            workload = f'workloads.{op}'
            for var in ['elapsed_time', 'user_cpu_time', 'sys_cpu_time', 'total_events',
                        'mean_latency_sec', 'max_latency_sec', 'p95_latency_sec']:
                accumulators.append(f'{workload}.{var}')
            for var in self._sysbench_vars_to_copy:
                vars_to_copy.append(f'{workload}.{re.sub(r":.*", "", var)}')
        self._add_accumulators(accumulators)
        self._add_fields_to_copy(vars_to_copy)

    def __update_report(self, dest: dict, source: dict, sample_row: dict = None):
        if self._is_fileio:
            self.__update_report_fileio(dest, source, sample_row)
        else:
            self.__update_report_simple(dest, source, sample_row)

    def __update_report_simple(self, dest: dict, source: dict, sample_row: dict = None):
        if sample_row is None:
            sample_row = source
        for op in self._sysbench_operations:
            pop = f'workload: {op}'
            dest[pop] = {}
            dest[pop]['Elapsed Time'] = self._fformat(self._summary['data_run_interval'], 3)
            dest[pop]['CPU Time'] = self._fformat(source[op]['user_cpu_time'] + source[op]['sys_cpu_time'], 3)
            for var in ['total_events:precision=3:suffix=events:base=1000:integer=1']:
                self._copy_formatted_value(var, dest[pop], source[op])
            for var in self._sysbench_vars_to_copy:
                self._copy_formatted_value(var, dest[pop], source[op])
            source[op]['events_rate'] = self._safe_div(source[op]['total_events'],
                                                       self._summary['data_run_interval'], number_only=True)
            dest[pop]['events_rate'] = self._prettyprint(self._safe_div(source[op]['total_events'],
                                                                        self._summary['data_run_interval']),
                                                         precision=3, base=1000, suffix='events/sec')

    def __update_report_fileio(self, dest: dict, source: dict, sample_row: dict = None):
        if sample_row is None:
            sample_row = source
        for op in self._sysbench_operations:
            pop = f'workload: {op}'
            dest[pop] = {}
            dest[pop]['Elapsed Time'] = self._fformat(source[op]['op_elapsed_time'], 3)
            dest[pop]['CPU Time'] = self._fformat(source[op]['user_cpu_time'] + source[op]['sys_cpu_time'], 3)
            for var in ['read_ops:precision=3:suffix=ops:base=1000:integer=1',
                        'write_ops:precision=3:suffix=ops:base=1000:integer=1',
                        'fsync_ops:precision=3:suffix=ops:base=1000:integer=1',
                        'files:precision=3:suffix='':base=1000:integer=1']:
                self._copy_formatted_value(var, dest[pop], source[op])
            for var in self._sysbench_vars_to_copy:
                self._copy_formatted_value(var, dest[pop], source[op])
            source[op]['read_ops_rate'] = self._safe_div(source[op]['read_ops'], source[op]['elapsed_time'], number_only=True)
            source[op]['write_ops_rate'] = self._safe_div(source[op]['write_ops'], source[op]['elapsed_time'], number_only=True)
            source[op]['read_data_rate'] = self._safe_div(source[op]['blocksize'] * source[op]['read_ops'],
                                                          source[op]['elapsed_time'], number_only=True)
            source[op]['write_data_rate'] = self._safe_div(source[op]['blocksize'] * source[op]['write_ops'],
                                                           source[op]['elapsed_time'], number_only=True)
            dest[pop]['read ops rate'] = self._prettyprint(self._safe_div(source[op]['read_ops'], source[op]['elapsed_time']),
                                                           precision=3, base=1000, suffix='ops/sec')
            dest[pop]['write ops rate'] = self._prettyprint(self._safe_div(source[op]['write_ops'], source[op]['elapsed_time']),
                                                            precision=3, base=1000, suffix='ops/sec')
            dest[pop]['read data rate'] = self._prettyprint(self._safe_div(source[op]['blocksize'] * source[op]['read_ops'],
                                                                           source[op]['elapsed_time']),
                                                            precision=3, base=1024, suffix='B/sec')
            dest[pop]['write data rate'] = self._prettyprint(self._safe_div(source[op]['blocksize'] * source[op]['write_ops'],
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
