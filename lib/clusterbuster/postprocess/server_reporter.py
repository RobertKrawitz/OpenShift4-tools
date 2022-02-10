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
from lib.clusterbuster.postprocess.VerboseHeader import VerboseHeader

class server_reporter(Reporter):
    def __init__(self, jdata: dict, report_format: str):
        Reporter.__init__(self, jdata, report_format)
        self._summary['total_max_round_trip_time'] = 0
        self._summary['round_trip_time_accumulator'] = 0
        self._summary['total_data_xfer_bytes'] = 0
        self._summary['total_iterations'] = 0

    def create_row(self, row: dict):
        rowhash = self._rows[Reporter.create_row(self, row)]
        rowhash['mean_round_trip_time_msec'] = row['mean_latency_sec'] * 1000
        rowhash['max_round_trip_time_msec'] = row['max_latency_sec'] * 1000
        rowhash['iterations'] = row['passes']
        rowhash['data_xfer'] = row['data_sent_bytes']
        rowhash['data_rate_mb_sec'] = rowhash['data_xfer'] / rowhash['runtime'] / 1000000
        if rowhash['max_round_trip_time_msec'] > self._summary['total_max_round_trip_time']:
            self._summary['total_max_round_trip_time'] = rowhash['max_round_trip_time_msec']
        self._summary['total_data_xfer_bytes'] += rowhash['data_xfer']
        self._summary['total_iterations'] += rowhash['iterations']
        self._summary['round_trip_time_accumulator'] += rowhash['mean_round_trip_time_msec']

    def print_summary(self):
        # I'd like to do this, but if the nodes are out of sync time-wise, this will not
        # function correctly.
        Reporter.print_summary(self)
        if self._all_clients_are_on_the_same_node:
            self._summary['average_data_rate_mb_sec'] = self._summary['total_data_xfer_bytes'] / (self._summary['last_end'] - self._summary['first_start']) / 1000000
        else:
            self._summary['average_data_rate_mb_sec'] = self._summary['total_data_xfer_bytes'] / self._summary['elapsed_time_average'] / 1000000
        self._summary['max_round_trip_time_msec'] = self._summary['total_max_round_trip_time']
        self._summary['average_data_rate_mb_sec'] = self._summary['total_data_xfer_bytes'] / self._summary['elapsed_time_average'] / 1000000
        self._summary['average_round_trip_time_msec'] = self._summary['round_trip_time_accumulator'] / self._summary['total_instances']
        print(f"""    Total Messages Sent:        {self._summary['total_iterations']}
    Total Data Sent (MB):       {round(self._summary['total_data_xfer_bytes'] / 1000000, 3)}
    Average Data Rate (MB/sec): {round(self._summary['average_data_rate_mb_sec'], 3)}
    Average RTT msec:           {round(self._summary['average_round_trip_time_msec'], 3)}
    Max RTT msec:               {round(self._summary['max_round_trip_time_msec'], 3)}""")

    def print_verbose(self):
        lastNamespace = None
        lastPod = None
        lastContainer = None
        self._rows.sort(key=self.row_name)
        header = VerboseHeader(['namespace', 'pod', 'container'])
        for row in self._rows:
            Reporter.print_verbose(row)
            header.print_header(row)
            print(f"""            Elapsed Time:       {round(row['runtime'], 3)}
            Messages Sent:      {row['iterations']}
            Data Sent:          {round(row['data_xfer'] / 1000000, 3)}
            Data Rate (MB/sec): {round(row['data_rate_mb_sec'], 3)}
            Avg RTT msec:       {round(row['mean_round_trip_time_msec'], 3)}
            Max RTT msec:       {round(row['max_round_trip_time_msec'], 3)}
""")
