#!/usr/bin/env python3
# Copyright 2023 Robert Krawitz/Red Hat
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


class AnalyzePostprocess:
    """
    Post-process ClusterBuster analysis
    """

    def __init__(self, report, status, metadata):
        self._report = report
        self._status = status
        self._metadata = metadata

    def Postprocess(self):
        self._report['metadata'] = {
            'uuid': None,
            'run_host': None,
            'openshift_version': None,
            'kata_version': None,
            'result': None,
            'job_start': None,
            'job_end': None,
            'job_runtime': None,
            }
        for job, job_status in self._status['jobs'].items():
            for var in ['result', 'job_start', 'job_end', 'job_runtime']:
                if self._report['metadata'][var] is None:
                    self._report['metadata'][var] = job_status.get(var, None)
                elif job_status.get(var, None) is not None and job_status[var] != self._report['metadata'][var]:
                    raise Exception(f'Mismatched {var} in status ({job_status[var]} vs {self._report["metadata"][var]}!')
        for job, job_metadata in self._metadata['jobs'].items():
            for var in ['uuid', 'run_host', 'openshift_version', 'kata_version']:
                if self._report['metadata'][var] is None:
                    self._report['metadata'][var] = job_metadata.get(var, None)
                elif job_metadata.get(var, None) is not None and job_metadata[var] != self._report['metadata'][var]:
                    raise Exception(f'Mismatched {var} in metadata ({job_metadata[var]} vs {self._report["metadata"][var]}!')
        return self._report
