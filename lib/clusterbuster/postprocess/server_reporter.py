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
from lib.clusterbuster.postprocess.Reporter import Reporter

class server_reporter(Reporter):
    def __init__(self, jdata: dict, report_format: str):
        Reporter.__init__(self, jdata, report_format)
        self.initialize_accumulators(['data_sent_bytes', 'passes', 'mean_latency_sec', 'max_latency_sec'])
        self.set_header_components(['namespace', 'pod', 'container'])

    def create_summary(self):
        Reporter.create_summary(self)
        self._summary['max_latency_sec'] = self._summary['max_max_latency_sec']
        self._summary['average_data_rate_mb_sec'] = self._summary['data_sent_bytes'] / self._summary['elapsed_time_average'] / 1000000
        self._summary['average_round_trip_time_msec'] = self._summary['mean_latency_sec'] / self._summary['total_instances']

    def print_summary(self):
        # I'd like to do this, but if the nodes are out of sync time-wise, this will not
        # function correctly.
        Reporter.print_summary(self)
        self.print_summary_key_value('Total Messages Sent', self._summary['passes'])
        self.print_summary_key_value('Total Data Sent (MB)', round(self._summary['data_sent_bytes'] / 1000000, 3))
        self.print_summary_key_value('Average Data Rate (MB/sec)', round(self._summary['average_data_rate_mb_sec'], 3))
        self.print_summary_key_value('Average RTT msec', round(self._summary['average_round_trip_time_msec'], 3))
        self.print_summary_key_value('Max RTT msec', round(self._summary['max_latency_sec'], 3))

    def print_verbose(self, row):
        Reporter.print_verbose(self, row)
        self.print_verbose_key_value('Elapsed Time', round(row['data_elapsed_time'], 3))
        self.print_verbose_key_value('Messages Sent', row['passes'])
        self.print_verbose_key_value('Data Sent',  round(row['data_sent_bytes'], 3))
        self.print_verbose_key_value('Data Rate (MB/sec)', round(row['data_sent_bytes'] / row['data_elapsed_time'] / 1000000, 3))
        self.print_verbose_key_value('Avg RTT msec', round(row['mean_latency_sec'], 3))
        self.print_verbose_key_value('Max RTT msec', round(row['max_latency_sec'], 3))
