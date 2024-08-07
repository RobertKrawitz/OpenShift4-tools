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

from ..ClusterBusterAnalysis import ClusterBusterAnalysisException, ClusterBusterPostprocessBase
import argparse


class _ClusterBusterAnalysisJobMismatchException(ClusterBusterAnalysisException):
    def __init__(self, var: str, job: str, val1, val2):
        super().__init__(f"Mismatched {var} in {job}: ({val1} vs {val2})")


class AnalyzePostprocess(ClusterBusterPostprocessBase):
    """
    Post-process ClusterBuster analysis
    """

    def __init__(self, report, status, metadata, extras=None):
        super().__init__(report, status, metadata, extras=extras)
        parser = argparse.ArgumentParser(description="ClusterBuster loader")
        parser.add_argument('--allow-mismatch', action='store_true')
        self._args, self._extra_args = parser.parse_known_args(extras)

    def __CheckMatch(self, job: str, var: str, you: dict):
        if var in self._report['metadata']:
            if self._report['metadata'][var] is None:
                self._report['metadata'][var] = you.get(var, None)
            elif you.get(var, None) is not None and you[var] != self._report['metadata'][var]:
                raise _ClusterBusterAnalysisJobMismatchException(var, job, you[var],
                                                                 self._report['metadata'][var])

    def Postprocess(self):
        self._report['metadata'] = {
            'uuid': None,
            'run_host': None,
            'openshift_version': None,
            'kata_containers_version': None,
            'kata_version': None,
            'result': None,
            'job_start': None,
            'job_end': None,
            'job_runtime': None,
            }
        if not self._args.allow_mismatch:
            for job, job_status in self._status['jobs'].items():
                for var in self.job_status_vars():
                    self.__CheckMatch(job, var, job_status)
            for job, job_metadata in self._metadata['jobs'].items():
                for var in self.job_metadata_vars():
                    self.__CheckMatch(job, var, job_metadata)
        return self._report
