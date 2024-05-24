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


class files_analysis(SpreadsheetAnalysis):
    """
    Analyze uperf data
    """

    def __init__(self, workload: str, data: dict, metadata: dict):
        dimensions = ['By Pod Count', 'By Dirs', 'By Files', 'By Blocksize', 'By Filesize', 'By Direct']
        variables = [
            {
             'var': 'create.elapsed_time',
             'name': 'Create Elapsed Time',
             'base': 0,
             'unit': ' (Sec)',
             },
            {
             'var': 'read.elapsed_time',
             'name': 'Read Elapsed Time',
             'base': 0,
             'unit': ' (Sec)',
             },
            {
             'var': 'remove.elapsed_time',
             'name': 'Remove Elapsed Time',
             'base': 0,
             'unit': ' (Sec)',
             },
            ]
        super().__init__(workload, data, metadata, dimensions, variables)

    def _retrieve_datum(self, var: str, value: dict):
        op, metric = var.split('.')
        return value[op].get(metric, 0)
