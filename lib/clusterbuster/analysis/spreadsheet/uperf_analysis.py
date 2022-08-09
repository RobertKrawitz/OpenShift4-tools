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

from .analyze_spreadsheet_generic import SpreadsheetAnalysis


class uperf_analysis(SpreadsheetAnalysis):
    """
    Analyze uperf data
    """

    def __init__(self, workload: str, data: dict, metadata: dict):
        dimensions = ['By Pod Count', 'By Message Size', 'By Threads']
        variables = [
            {
             'var': 'rate',
             'name': 'Rate',
             'unit': ' (MB/sec)',
             'multiplier': .000001
             },
            {
             'var': 'avg_time_op',
             'name': 'Latency',
             'unit': ' (usec)',
             'multiplier': 1000000
             }
             ]
        SpreadsheetAnalysis.__init__(self, workload, data, metadata, dimensions, variables)