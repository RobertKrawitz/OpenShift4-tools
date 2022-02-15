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

import json
import sys
import textwrap
from copy import deepcopy
from lib.clusterbuster.postprocess.ClusterBusterReporter import ClusterBusterReporter

class sysbench_reporter(ClusterBusterReporter):
    def __init__(self, jdata: dict, report_format: str):
        ClusterBusterReporter.__init__(self, jdata, report_format)
        self._sysbench_operations = jdata['metadata']['options']['workloadOptions']['sysbench_fileio_tests']
        self._sysbench_vars_to_copy = ['filesize', 'blocksize', 'rdwr_ratio',
                                       'fsync_frequency', 'final_fsync_enabled', 'io_mode']
        accumulators = []
        vars_to_copy = []
        for op in self._sysbench_operations:
            workload=f'workloads.{op}'
            for var in ['elapsed_time', 'user_cpu_time', 'sys_cpu_time',
                        'read_ops', 'write_ops', 'fsync_ops',
                        'mean_latency_sec', 'max_latency_sec', 'p95_latency_sec', 'files']:
                accumulators.append(f'{workload}.{var}')
            for var in self._sysbench_vars_to_copy:
                vars_to_copy.append(f'{workload}.{var}')
        self.initialize_accumulators(accumulators)
        self.initialize_fields_to_copy(vars_to_copy)
        self.set_header_components(['namespace', 'pod', 'container', 'process_id'])
        self.set_summary_header_components(['Workload'])

    def __update_report(self, dest: dict, source: dict, sample_row:dict = None):
        if sample_row is None:
            sample_row = source
        print(sample_row)
        for op in self._sysbench_operations:
            dest[op] = {}
            dest[op]['Elapsed Time'] = round(source[op]['elapsed_time'], 3)
            dest[op]['CPU Time'] = round(source[op]['user_cpu_time'] + source[op]['sys_cpu_time'], 3)
            for key in ['read_ops', 'write_ops', 'fsync_ops', 'files']:
                dest[op][key] = source[op][key]
            for var in self._sysbench_vars_to_copy:
                dest[op][var] = sample_row[op][var]

    def generate_summary(self, results: dict):
        # I'd like to do this, but if the nodes are out of sync time-wise, this will not
        # function correctly.
        ClusterBusterReporter.generate_summary(self, results)
        sample_row = self._jdata['Results'][0]['workloads']
        self.__update_report(results, self._summary['workloads'], sample_row)

    def generate_row(self, results: dict, row: dict):
        ClusterBusterReporter.generate_row(self, results, row)
        result = {}
        self.__update_report(result, row['workloads'])
        results[row['namespace']][row['pod']][row['container']][row['process_id']] = result
