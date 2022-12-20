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

from ..ClusterBusterAnalysis import ClusterBusterAnalyzeOne
from math import log, exp


class FilesAnalysisBase(ClusterBusterAnalyzeOne):
    """
    Analyze files data
    """

    def __init__(self, workload: str, data: dict, metadata: dict):
        super().__init__(workload, data, metadata)
        self._baseline = self._metadata['baseline']

    def Analyze(self, report_summary: bool = True, report_detail: bool = False):
        detail = dict()
        answer = {
            'workload': self._workload,
            }
        summary = dict()
        count = dict()
        ratio = dict()
        times = dict()
        known_ops = dict()
        known_subops = dict()
        for pods, data1 in self._data.items():
            for dirs, data2 in data1.items():
                for files, data3 in data2.items():
                    for blocksize, data4 in data3.items():
                        for filesize, data5 in data4.items():
                            for direct, data6 in data5.items():
                                if direct == 0:
                                    continue
                                case_label = f'Pods: {pods}, Dirs: {dirs}, Files: {files}, Blocksize: {blocksize}, Filesize: {filesize}'
                                detail_row = dict()
                                for runtime, data7 in data6.items():
                                    if runtime not in summary:
                                        summary[runtime] = dict()
                                        count[runtime] = dict()
                                    for op, data8 in data7.items():
                                        if op not in detail_row:
                                            detail_row[op] = dict()
                                        known_ops[op] = 1
                                        if op not in times:
                                            times[op] = {}
                                        if op not in summary[runtime]:
                                            summary[runtime][op] = dict()
                                            count[runtime][op] = dict()
                                        for subop, val in data8.items():
                                            known_subops[subop] = 1
                                            if subop not in detail_row[op]:
                                                detail_row[op][subop] = dict()
                                            if subop not in times[op]:
                                                times[op][subop] = dict()
                                            if runtime not in times[op][subop]:
                                                times[op][subop][runtime] = list()
                                            times[op][subop][runtime].append(val)
                                            if val > 0:
                                                detail_row[op][subop][runtime] = val
                                                if subop not in summary[runtime][op]:
                                                    summary[runtime][op][subop] = 0
                                                    count[runtime][op][subop] = 0
                                                count[runtime][op][subop] += 1
                                                summary[runtime][op][subop] += log(val)
                                    if runtime != self._baseline:
                                        for op, detail1 in detail_row.items():
                                            for subop, detail2 in detail1.items():
                                                detail2['ratio'] = detail2[runtime] / detail2[self._baseline]
                                    if len(detail_row.keys()) > 0:
                                        detail[case_label] = detail_row
        if summary.keys():
            for run, data1 in summary.items():
                answer[run] = dict()
                for op, data2 in data1.items():
                    answer[run][op] = dict()
                    for subop, data3 in data2.items():
                        answer[run][op][subop] = exp(summary[run][op][subop] / count[run][op][subop])
                if run == self._baseline:
                    continue
                answer[run]['ratio'] = dict()
                for op, data1 in answer[self._baseline].items():
                    if op not in answer[run]['ratio']:
                        answer[run]['ratio'][op] = dict()
                    for subop, data2 in data1.items():
                        answer[run]['ratio'][op][subop] = answer[run][op][subop] / answer[self._baseline][op][subop]
                answer[run]['min_ratio'] = dict()
                answer[run]['max_ratio'] = dict()
                for op in known_ops.keys():
                    if op not in times:
                        continue
                    if op not in answer[run]['min_ratio']:
                        answer[run]['min_ratio'][op] = dict()
                        answer[run]['max_ratio'][op] = dict()
                    for subop in known_subops.keys():
                        if subop not in times[op]:
                            continue
                        min_ratio = None
                        max_ratio = None
                        for i in range(len(times[op][subop][self._baseline])):
                            if times[op][subop][self._baseline][i] > 0 and times[op][subop][self._baseline][i] > 0:
                                ratio = times[op][subop][run][i] / times[op][subop][self._baseline][i]
                                if min_ratio is None or ratio < min_ratio:
                                    min_ratio = ratio
                                if max_ratio is None or ratio > max_ratio:
                                    max_ratio = ratio
                        answer[run]['min_ratio'][op][subop] = min_ratio
                        answer[run]['max_ratio'][op][subop] = max_ratio
        if report_summary:
            if report_detail:
                return answer, detail
            else:
                return answer
        else:
            if report_detail:
                return detail


class files_analysis(FilesAnalysisBase):
    def __init__(self, workload: str, data: dict, metadata: dict):
        super().__init__(workload, data, metadata)
