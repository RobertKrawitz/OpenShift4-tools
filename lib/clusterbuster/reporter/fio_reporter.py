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

import base64
from lib.clusterbuster.reporter.ClusterBusterReporter import ClusterBusterReporter


class fio_reporter(ClusterBusterReporter):
    def __init__(self, jdata: dict, report_format: str):
        ClusterBusterReporter.__init__(self, jdata, report_format)
        self._fio_operations = ['read', 'write', 'trim']
        self._fio_vars = ['io_kbytes', 'total_ios', 'runtime',
                          'slat_ns.max', 'slat_ns.mean',
                          'clat_ns.max', 'clat_ns.mean',
                          'lat_ns.max', 'lat_ns.mean']
        accumulators = []
        for op in self._fio_operations:
            workload = f'results.jobs.{op}'
            for var in self._fio_vars:
                accumulators.append(f'{workload}.{var}')
        accumulators.append('results.jobs.sync.total_ios')
        accumulators.append('results.jobs.sync.lat_ns.max')
        accumulators.append('results.jobs.sync.lat_ns.mean')
        self._add_accumulators(accumulators)
        self._set_header_components(['namespace', 'pod', 'container', 'operation'])
        self._set_summary_header_components(['operation'])

    def __update_report(self, dest: dict, source: dict, sample_row: dict = None):
        if sample_row is None:
            sample_row = source
        for op in self._fio_operations:
            if op not in dest:
                dest[op] = {}
            dest[op]['io_kbytes'] = self._fformat(source[op]['io_kbytes'], 0)
            dest[op]['total_ios'] = self._fformat(source[op]['total_ios'], 0)
            if 'runtime_counter' in source[op] and source[op]['runtime_counter'] > 0:
                divisor = source[op]['runtime_counter']
            else:
                divisor = 1
            dest[op]['runtime_sec'] = self._fformat(source[op]['runtime'] / divisor / 1000.0, 3)
            dest[op]['io_mb/sec'] = self._safe_div(source[op]['io_kbytes'] / 1000.0,
                                                   source[op]['runtime'] / divisor / 1000.0, 3)
            dest[op]['slat_max_ms'] = self._fformat(source[op]['slat_ns']['max_max'] / 1000000.0, 3)
            dest[op]['slat_mean_ms'] = self._fformat(source[op]['slat_ns']['mean'] / 1000000.0, 3)
            dest[op]['clat_max_ms'] = self._fformat(source[op]['clat_ns']['max_max'] / 1000000.0, 3)
            dest[op]['clat_mean_ms'] = self._fformat(source[op]['clat_ns']['mean'] / 1000000.0, 3)
            dest[op]['lat_max_ms'] = self._fformat(source[op]['lat_ns']['max_max'] / 1000000.0, 3)
            dest[op]['lat_mean_ms'] = self._fformat(source[op]['lat_ns']['mean'] / 1000000.0, 3)

    def _generate_summary(self, results: dict):
        # I'd like to do this, but if the nodes are out of sync time-wise, this will not
        # function correctly.
        ClusterBusterReporter._generate_summary(self, results)
        sample_row = self._jdata['Results'][0]['results']
        results['FIO version'] = sample_row['fio version']
        results['Sub-jobs'] = len(sample_row['jobs'])
        for k, v in sample_row['global options'].items():
            results[k] = v
        self.__update_report(results, self._summary['results'], sample_row)
        results['FIO job file'] = base64.b64decode(self._jdata['metadata']['options']['workloadOptions']['fio_job_file']).decode()

    def _generate_row(self, results: dict, row: dict):
        ClusterBusterReporter._generate_row(self, results, row)
        result = {}
        for op in self._fio_operations:
            result[op] = {}
            result[op]['io_kbytes'] = self._fformat(row['results'][op]['io_kbytes'], 0)
            result[op]['total_ios'] = self._fformat(row['results'][op]['total_ios'], 0)
            if 'runtime_counter' in row['results'][op] and row['results'][op]['runtime_counter'] > 0:
                divisor = row['results'][op]['runtime_counter']
            else:
                divisor = 1
            result[op]['runtime_sec'] = self._fformat(row['results'][op]['runtime'] / divisor / 1000.0, 3)
            result[op]['io_mb/sec'] = self._safe_div(row['results'][op]['io_kbytes'] / 1000.0,
                                                     row['results'][op]['runtime'] / divisor / 1000.0, 3)
            result[op]['slat_max_ms'] = self._fformat(row['results'][op]['slat_ns']['max'] / 1000000.0, 3)
            result[op]['slat_mean_ms'] = self._fformat(row['results'][op]['slat_ns']['mean'] / 1000000.0, 3)
            result[op]['clat_max_ms'] = self._fformat(row['results'][op]['clat_ns']['max'] / 1000000.0, 3)
            result[op]['clat_mean_ms'] = self._fformat(row['results'][op]['clat_ns']['mean'] / 1000000.0, 3)
            result[op]['lat_max_ms'] = self._fformat(row['results'][op]['lat_ns']['max'] / 1000000.0, 3)
            result[op]['lat_mean_ms'] = self._fformat(row['results'][op]['lat_ns']['mean'] / 1000000.0, 3)
        results[row['namespace']][row['pod']][row['container']] = result
