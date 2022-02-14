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

class server_reporter(ClusterBusterReporter):
    def __init__(self, jdata: dict, report_format: str):
        ClusterBusterReporter.__init__(self, jdata, report_format)
        self.initialize_accumulators(['data_sent_bytes', 'passes', 'mean_latency_sec', 'max_latency_sec'])
        self.set_header_components(['namespace', 'pod', 'container'])

    def initialize_summary(self):
        ClusterBusterReporter.initialize_summary(self)
        self._summary['max_latency_sec'] = self._summary['max_max_latency_sec']
        self._summary['average_data_rate_mb_sec'] = self._summary['data_sent_bytes'] / self._summary['elapsed_time_average'] / 1000000
        self._summary['average_round_trip_time_msec'] = self._summary['mean_latency_sec'] / self._summary['total_instances']

    def generate_summary(self, results: dict):
        # I'd like to do this, but if the nodes are out of sync time-wise, this will not
        # function correctly.
        ClusterBusterReporter.generate_summary(self, results)
        results['Total Messages Sent'] = self._summary['passes']
        results['Total Data Sent (MB)'] = round(self._summary['data_sent_bytes'] / 1000000, 3)
        results['Average Data Rate (MB/sec)'] = round(self._summary['average_data_rate_mb_sec'], 3)
        results['Average RTT msec'] = round(self._summary['average_round_trip_time_msec'], 3)
        results['Max RTT msec'] = round(self._summary['max_latency_sec'], 3)

    def generate_row(self, results: dict, row: dict):
        ClusterBusterReporter.generate_row(self, results, row)
        result = {}
        result['Elapsed Time'] = round(row['data_elapsed_time'], 3)
        result['Messages Sent'] = row['passes']
        result['Data Sent (MB)'] =  round(row['data_sent_bytes'] / 1000000, 3)
        result['Data Rate (MB/sec)'] = round(row['data_sent_bytes'] / row['data_elapsed_time'] / 1000000, 3)
        result['Avg RTT msec'] = round(row['mean_latency_sec'], 3)
        result['Max RTT msec'] = round(row['max_latency_sec'], 3)
        results[row['namespace']][row['pod']][row['container']] = result
