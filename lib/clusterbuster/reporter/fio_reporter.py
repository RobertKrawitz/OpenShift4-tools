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
        self._jobs = jdata['metadata']['workload_metadata']['jobs']
        self._job_names = list(self._jobs.keys())
        self._fio_operations = ['read', 'write', 'trim']
        self._fio_vars = ['io_kbytes', 'total_ios', 'runtime',
                          'slat_ns.max', 'slat_ns.mean',
                          'clat_ns.max', 'clat_ns.mean',
                          'lat_ns.max', 'lat_ns.mean']
        accumulators = []
        for job in self._job_names:
            for op in self._fio_operations:
                workload = f'results.{job}.job_results.jobs.{op}'
                for var in self._fio_vars:
                    accumulators.append(f'{workload}.{var}')
            accumulators.append('results.{job}.job_results.jobs.sync.total_ios')
            accumulators.append('results.{job}.job_results.jobs.sync.lat_ns.max')
            accumulators.append('results.{job}.job_results.jobs.sync.lat_ns.mean')
        self._add_accumulators(accumulators)
        self._set_header_components(['namespace', 'pod', 'container', 'job', 'operation'])
        self._set_summary_header_components(['job', 'operation'])

    def __update_report(self, dest: dict, source: dict, max_key: str, rows: int = 1):
        for job in self._job_names:
            if job not in dest:
                dest[job] = {}
            for op in self._fio_operations:
                source1 = source[job]['job_results'][op]
                if source1['io_kbytes'] > 0:
                    if op not in dest:
                        dest[job][op] = {}
                    dest1 = dest[job][op]
                    dest1['io_kbytes'] = self._fformat(source1['io_kbytes'], 0)
                    dest1['total_ios'] = self._fformat(source1['total_ios'], 0)
                    if 'runtime_counter' in source1 and source1['runtime_counter'] > 0:
                        divisor = source1['runtime_counter']
                    else:
                        divisor = 1
                    dest1['runtime_sec'] = self._fformat(source1['runtime'] / divisor / rows / 1000.0, 3)
                    dest1['io_mb/sec'] = self._safe_div(source1['io_kbytes'] / 1000.0,
                                                           source1['runtime'] / divisor / 1000.0, 3)
                    dest1['slat_max_ms'] = self._fformat(source1['slat_ns'][max_key] / 1000000.0, 3)
                    dest1['slat_mean_ms'] = self._fformat(source1['slat_ns']['mean'] / rows / 1000000.0, 3)
                    dest1['clat_max_ms'] = self._fformat(source1['clat_ns'][max_key] / 1000000.0, 3)
                    dest1['clat_mean_ms'] = self._fformat(source1['clat_ns']['mean'] / rows / 1000000.0, 3)
                    dest1['lat_max_ms'] = self._fformat(source1['lat_ns'][max_key] / 1000000.0, 3)
                    dest1['lat_mean_ms'] = self._fformat(source1['lat_ns']['mean'] / rows / 1000000.0, 3)

    def _generate_summary(self, results: dict):
        # I'd like to do this, but if the nodes are out of sync time-wise, this will not
        # function correctly.
        ClusterBusterReporter._generate_summary(self, results)
        sample_row = self._jdata['Results'][0]['results'][self._job_names[0]]['job_results']
        results['FIO version'] = sample_row['fio version']
        for k, v in sample_row['global options'].items():
            if k not in ['rw', 'bs']:
                results[k] = v
        self.__update_report(results, self._summary['results'], 'max_max', int(self._summary['total_instances']))
        results['FIO job file'] = base64.b64decode(self._jdata['metadata']['options']['workloadOptions']['fio_job_file']).decode()

    def _generate_row(self, results: dict, row: dict):
        ClusterBusterReporter._generate_row(self, results, row)
        result = {}
        self.__update_report(result, row['results'], 'max')
        self._insert_into(results, [row['namespace'], row['pod'], row['container']], result)
