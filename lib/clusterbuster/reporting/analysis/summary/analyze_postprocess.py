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


from ..ClusterBusterAnalysis import ClusterBusterPostprocessBase


class AnalyzePostprocess(ClusterBusterPostprocessBase):
    """
    Post-process ClusterBuster analysis
    """

    def __init__(self, report, status, metadata, extras=None):
        super().__init__(report, status, metadata, extras=extras)

    def Postprocess(self):
        metadata = {}
        for job, job_status in self._status['jobs'].items():
            if job not in metadata:
                metadata[job] = {}
            for var in self.job_status_vars():
                if var in job_status:
                    metadata[job][var] = job_status[var]
        for job, job_metadata in self._metadata['jobs'].items():
            if job not in metadata:
                metadata[job] = {}
            for var in self.job_metadata_vars():
                if var in job_metadata:
                    metadata[job][var] = job_metadata[var]
        self._report['metadata'] = metadata
        return self._report
