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

import base64
from .ClusterBusterReporter import ClusterBusterReporter


class fio_reporter(ClusterBusterReporter):
    def __init__(self, jdata: dict, report_format: str, extras=None):
        super().__init__(jdata, report_format, extras=extras)
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
        self._set_header_components(['namespace', 'pod', 'container', 'process_id'])

    def __update_report(self, dest: dict, source: dict, max_key: str, rows: int = 1):
        for job in self._job_names:
            pjob = f'job: {job}'
            if pjob not in dest:
                dest[pjob] = {}
            for op in self._fio_operations:
                pop = f'operation: {op}'
                source1 = source[job]['job_results'][op]
                if source1['io_kbytes'] > 0:
                    if pop not in dest:
                        dest[pjob][pop] = {}
                    dest1 = dest[pjob][pop]
                    ios = source1['total_ios']
                    nbytes = source1['io_kbytes'] * 1024
                    runtime = source1['runtime'] / rows / 1000.0
                    dest1['io_bytes'] = self._prettyprint(nbytes, precision=3, suffix='B', integer=1)
                    dest1['total_ios'] = self._prettyprint(ios, base=1000, precision=3, integer=1)
                    dest1['runtime'] = self._prettyprint(runtime, base=1000, precision=3, suffix='sec')
                    source1['data_rate'] = self._safe_div(nbytes, runtime, number_only=True)
                    source1['io_rate'] = self._safe_div(ios, runtime, number_only=True)
                    dest1['io_data_rate'] = self._prettyprint(self._safe_div(nbytes, runtime),
                                                              precision=3, suffix='B/sec')
                    dest1['io_rate'] = self._prettyprint(self._safe_div(ios, runtime),
                                                         precision=3, base=1000, suffix='/sec')
                    dest1['slat_max'] = self._prettyprint(source1['slat_ns'][max_key] / 1000000000.0,
                                                          base=1000, precision=3, suffix='sec')
                    dest1['slat_mean'] = self._prettyprint(source1['slat_ns']['mean'] / rows / 1000000000.0,
                                                           base=1000, precision=3, suffix='sec')
                    dest1['clat_max'] = self._prettyprint(source1['clat_ns'][max_key] / 1000000000.0,
                                                          base=1000, precision=3, suffix='sec')
                    dest1['clat_mean'] = self._prettyprint(source1['clat_ns']['mean'] / rows / 1000000000.0,
                                                           base=1000, precision=3, suffix='sec')
                    dest1['lat_max'] = self._prettyprint(source1['lat_ns'][max_key] / 1000000000.0,
                                                         base=1000, precision=3, suffix='sec')
                    dest1['lat_mean'] = self._prettyprint(source1['lat_ns']['mean'] / rows / 1000000000.0,
                                                          base=1000, precision=3, suffix='sec')

    def _add_summary(self):
        ClusterBusterReporter._add_summary(self)
        for k, v in self._summary['results'].items():
            v['metadata'] = self._jdata['metadata']['workload_metadata']['jobs'][k]

    def _generate_summary(self, results: dict):
        # I'd like to do this, but if the nodes are out of sync time-wise, this will not
        # function correctly.
        ClusterBusterReporter._generate_summary(self, results)
        sample_row = self._jdata['Results']['worker_results'][0]['results'][self._job_names[0]]['job_results']
        results['FIO version'] = sample_row['fio version']
        for k, v in sample_row['global options'].items():
            if k not in ['rw', 'bs']:
                results[k] = v
        results['\nFIO job file'] = base64.b64decode(self._jdata['metadata']['options']['workloadOptions']['fio_job_file']).decode()
        results['\nJobs'] = {}
        self.__update_report(results['\nJobs'], self._summary['results'], 'max_max', int(self._summary['total_instances']))

    def _generate_row(self, results: dict, row: dict):
        ClusterBusterReporter._generate_row(self, results, row)
        result = {}
        self.__update_report(result, row['results'], 'max')
        self._insert_into(results, [row['namespace'], row['pod'], row['container'], str(row['process_id'])], result)
