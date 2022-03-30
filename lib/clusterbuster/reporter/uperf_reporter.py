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


class uperf_reporter(ClusterBusterReporter):
    def __init__(self, jdata: dict, report_format: str):
        ClusterBusterReporter.__init__(self, jdata, report_format)
        fields_to_copy = []
        self._jobs = jdata['metadata']['workload_metadata']['jobs']
        self._job_names = list(self._jobs.keys())
        self._uperf_operations = ['read', 'write', 'total']
        self._uperf_vars = ['nbytes', 'nops', 'elapsed_time']
        for op in self._uperf_operations:
            for v in ['avg', 'max']:
                self._uperf_vars.append(f'{op}.time_{v}')
        accumulators = []
        for job in self._job_names:
            fields_to_copy.append(f'results.{job}.status')
            workload = f'results.{job}.summary'
            for v in self._uperf_vars:
                accumulators.append(f'{workload}.{v}')
        self._add_fields_to_copy(fields_to_copy)
        self._add_accumulators(accumulators)
        self._set_header_components(['namespace', 'pod', 'container', 'job', 'summary', 'operation'])
        self._set_summary_header_components(['job', 'operation'])

    def __update_report(self, dest: dict, source: dict, max_key: str, rows: int = 1):
        for job in self._job_names:
            source1 = source[job]['summary']
            if source1['nbytes'] > 0:
                if job not in dest:
                    dest[job] = {}
                et = source1['elapsed_time']
                if 'elapsed_time_counter' in source1:
                    et = et / source1['elapsed_time_counter']
                    dest[job]['Avg Job Runtime'] = self._prettyprint(et, precision=3, suffix='sec')
                else:
                    dest[job]['Job Runtime'] = self._prettyprint(et, precision=3, suffix='sec')
                dest[job]['Total bytes'] = self._prettyprint(source1['nbytes'], precision=3, base=1000, suffix='B')
                dest[job]['Bytes/sec'] = self._prettyprint(self._safe_div(source1['nbytes'], et), precision=3, base=1000, suffix='B/sec')
                dest[job]['Total ops'] = self._prettyprint(source1['nops'], precision=3, base=1000, suffix=' ops')
                dest[job]['Ops/sec'] = self._prettyprint(self._safe_div(source1['nops'], et), precision=3, base=1000, suffix=' ops/sec')
                for op in self._uperf_operations:
                    if op in source1 and 'time_avg' in source1[op]:
                        if op not in dest:
                            dest[job][op] = {}
                        dest1 = dest[job][op]
                        dest1['Avg time/op'] = self._prettyprint(source1[op]['time_avg'], precision=3, base=1000, suffix='sec')
                        dest1['Max time/op'] = self._prettyprint(source1[op]['time_max'], precision=3, base=1000, suffix='sec')

    def _generate_summary(self, results: dict):
        # I'd like to do this, but if the nodes are out of sync time-wise, this will not
        # function correctly.
        ClusterBusterReporter._generate_summary(self, results)
        self.__update_report(results, self._summary['results'], 'max_max', int(self._summary['total_instances']))
        if 'failed' in self._jdata['Results']['worker_results'][0]:
            results['Failed jobs'] = {}
            for failure in self._jdata['Results']['worker_results'][0]['failed']:
                results['Failed jobs'][failure] = f'{self._jdata["Results"]["worker_results"][0]["results"][failure]["status"]["message"]})'

    def _generate_row(self, results: dict, row: dict):
        ClusterBusterReporter._generate_row(self, results, row)
        result = {}
        self.__update_report(result, row['results'], 'max')
        self._insert_into(results, [row['namespace'], row['pod'], row['container']], result)
