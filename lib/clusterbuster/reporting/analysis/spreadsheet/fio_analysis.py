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

from .analyze_spreadsheet_generic import SpreadsheetAnalysis


class fio_analysis(SpreadsheetAnalysis):
    """
    Analyze fio data
    """

    def __init__(self, workload: str, data: dict, metadata: dict):
        dimensions = ['By Pod Count', 'By Engine', 'By I/O Depth', '-By Fdatasync', 'By Direct', 'By Operation', 'By Blocksize']
        variables = [
            {
             'var': 'throughput',
             'name': 'Throughput',
             'unit': ' (MB/sec)',
             'multiplier': .000001
             },
            {
             'var': 'iops',
             'name': 'IO/sec',
             'base': 0,
             'detail': False
             },
            {
             'var': 'latency_avg',
             'name': 'Avg latency (msec)',
             'base': 0,
             'multiplier': .000001
             },
            {
             'var': 'latency_max',
             'name': 'Max latency (msec)',
             'base': 0,
             'multiplier': .000001
             }
             ]
        filters = {
            'By Direct': self.__filter_direct
            }
        super().__init__(workload, data, metadata, dimensions, variables, filters=filters)

    def __filter_direct(self, dimension, value):
        return value != 0

    def _retrieve_datum(self, var: str, value: dict):
        return value['total'].get(var, 0)
