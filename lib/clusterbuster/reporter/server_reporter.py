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


class server_reporter(ClusterBusterReporter):
    def __init__(self, jdata: dict, report_format: str):
        ClusterBusterReporter.__init__(self, jdata, report_format)
        self._add_accumulators(['data_sent_bytes', 'passes', 'mean_latency_sec', 'max_latency_sec'])
        self._set_header_components(['namespace', 'pod', 'container'])

    def _generate_summary(self, results: dict):
        # I'd like to do this, but if the nodes are out of sync time-wise, this will not
        # function correctly.
        ClusterBusterReporter._generate_summary(self, results)
        results['Total Messages Sent'] = self._prettyprint(self._summary['passes'],
                                                           integer=1, precision=3, base=1000, suffix='msgs')
        results['Total Data Sent'] = self._prettyprint(self._summary['data_sent_bytes'],
                                                       integer=1, precision=3, base=1000, suffix='B')
        self._summary['avg_data_rate'] = self._safe_div(self._summary['data_sent_bytes'],
                                                        self._summary['elapsed_time_average'], number_only=True)
        results['Average Data Rate'] = self._prettyprint(self._safe_div(self._summary['data_sent_bytes'],
                                                                        self._summary['elapsed_time_average']),
                                                         precision=3, base=1000, suffix='B/sec')
        self._summary['avg_latency'] = self._summary['mean_latency_sec'] / self._summary['total_instances']
        results['Average RTT'] = self._prettyprint(self._summary['mean_latency_sec'] / self._summary['total_instances'],
                                                   precision=3, base=1000, suffix='sec')
        results['Max RTT'] = self._prettyprint(self._summary['max_max_latency_sec'],
                                               precision=3, base=1000, suffix='sec')

    def _generate_row(self, results: dict, row: dict):
        ClusterBusterReporter._generate_row(self, results, row)
        result = {}
        result['Elapsed Time'] = self._fformat(row['data_elapsed_time'], 3)
        result['Messages Sent'] = self._prettyprint(row['passes'],
                                                    precision=3, integer=1, base=1000, suffix='msgs')
        result['Data Sent'] = self._prettyprint(row['data_sent_bytes'],
                                                precision=3, integer=1, base=1000, suffix='B')
        row['data_rate'] = self._safe_div(row['data_sent_bytes'], row['data_elapsed_time'], number_only=True)
        result['Data Rate'] = self._prettyprint(self._safe_div(row['data_sent_bytes'], row['data_elapsed_time']),
                                                precision=3, base=1000, suffix='B/sec')
        result['Average RTT'] = self._prettyprint(row['mean_latency_sec'],
                                                  precision=3, base=1000, suffix='sec')
        result['Max RTT'] = self._prettyprint(row['max_latency_sec'],
                                              precision=3, base=1000, suffix='sec')
        self._insert_into(results, [row['namespace'], row['pod'], row['container']], result)
