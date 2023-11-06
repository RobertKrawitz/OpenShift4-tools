#!/usr/bin/env python3

import os
import subprocess
import re
import json
import shutil

from clusterbuster_pod_client import clusterbuster_pod_client


class fio_client(clusterbuster_pod_client):
    """
    fio test for clusterbuster
    """

    def __init__(self):
        try:
            super().__init__()
            self._set_processes(int(self._args[0]))
            self.rundir = self._args[1]
            self.runtime = int(self._args[2])
            self.jobfilesdir = self._args[3]
            self.fio_blocksizes = self._toSizes(self._args[4])
            self.fio_patterns = re.split(r'\s+', self._args[5])
            self.fio_iodepths = self._toSizes(self._args[6])
            self.fio_fdatasyncs = self._toBools(self._args[7])
            self.fio_directs = self._toBools(self._args[8])
            if self._args[9]:
                self.fio_ioengines = re.split(r'\s+', self._args[9])
            else:
                self.fio_ioengines = []
            self.fio_ramptime = self._toSizes(self._args[10])
            self.fio_drop_cache = self._toBool(self._args[11])
            if self._args[12]:
                self.fio_generic_args = re.split(r'\s+', self._args[12])
            else:
                self.fio_generic_args = []
        except Exception as err:
            self._abort(f"Init failed! {err} {' '.join(self._args)}")

    def get_token(self, pattern: str, string: str, token: int = 1):
        match = re.match(pattern, string)
        if match:
            return match.group(token)
        else:
            return None

    def prepare_data_file(self, jobfile: str):
        with open(jobfile) as job:
            lines = [line.strip() for line in job.readlines()]
            for line in lines:
                if self.get_token(r'filename\s*=\s*(.+)', line):
                    filename = self.get_token(r'\s*filename\s*=\s*(.+)', line)
                elif self.get_token(r'size\s*=\s*([0-9]+)', line):
                    filesize = int(self.get_token(r'size\s*=\s*([0-9]+)', line))
        self._timestamp(f"  Job file {filename} will be size {filesize}")
        blocksize = 2 ** 20
        blocks = int((filesize + blocksize - 1) / blocksize)
        dirname = os.path.dirname(filename)
        if not self._isdir(dirname):
            os.makedirs(dirname)
        self._timestamp("Starting file creation")
        subprocess.run(['dd', 'if=/dev/zero', f'of={filename}', f'bs={str(blocksize)}', f'count={str(blocks)}'])
        self._timestamp("File created")

    def runone(self, jobfile: str):
        elapsed_time = 0
        all_results = {}
        data_start_time = self._adjusted_time()
        ucpu, scpu = self._cputimes()
        jobidx = 1
        self._timestamp(f"""
Sizes:       {self.fio_blocksizes}
Patterns:    {self.fio_patterns}
I/O depths:  {self.fio_iodepths}
Fdatasync:   {self.fio_fdatasyncs}
Direct I/O:  {self.fio_directs}
I/O engines: {self.fio_ioengines}
Drop cache:  {self.fio_drop_cache}""")
        self._timestamp("Creating workfile")
        self.prepare_data_file(jobfile)
        self._timestamp("Created workfile")
        for size in self.fio_blocksizes:
            for pattern in self.fio_patterns:
                for iodepth in self.fio_iodepths:
                    for fdatasync in self.fio_fdatasyncs:
                        for direct in self.fio_directs:
                            for ioengine in self.fio_ioengines:
                                jobname = '%04d-%s-%d-%d-%d-%d-%s' % (jobidx, pattern, size, iodepth, fdatasync, direct, ioengine)
                                if self.fio_drop_cache:
                                    self._drop_cache()
                                self._sync_to_controller(jobname)
                                if jobidx == 1:
                                    self._timestamp("Running...")
                                    data_start_time = self._adjusted_time()
                                jtime = self._adjusted_time()
                                jucpu, jscpu = self._cputimes()
                                command = ['fio', f'--rw={pattern}', f'--runtime={self.runtime}', f'--bs={size}',
                                           f'--iodepth={iodepth}', f'--fdatasync={int(fdatasync)}', f'--direct={int(direct)}',
                                           f'--ioengine={ioengine}', '--allow_file_create=0']
                                if not self.fio_drop_cache:
                                    command.append('--invalidate=0')
                                command.extend(self.fio_generic_args)
                                command.extend(['--output-format=json+', jobfile])
                                success, data, stderr = self.run_command(command)
                                if not success:
                                    raise Exception(f'{" ".join(command)} failed: {stderr if stderr != "" else "Unknown error"}')
                                result = json.loads(data)
                                jtime = self._adjusted_time(jtime)
                                jucpu, jscpu = self._cputimes(jucpu, jscpu)
                                elapsed_time += jtime
                                job_result = {
                                    'job_elapsed_time': jtime,
                                    'job_user_cpu_time': jucpu,
                                    'job_system_cpu_time': jscpu,
                                    'job_cpu_time': jucpu + jscpu,
                                    'job_results': result
                                    }
                                all_results[jobname] = job_result
                                jobidx = jobidx + 1
        if '-IGNORE-' not in jobfile:
            data_end_time = self._adjusted_time()
            ucpu, scpu = self._cputimes(ucpu, scpu)
            extras = {
                'results': all_results
                }
            self._report_results(data_start_time, data_end_time, elapsed_time, ucpu, scpu, extras)

    def get_jobfiles(self, jobfiledir: str, tmpdir: str, localid: str):
        new_jobfiles = []
        with os.scandir(jobfiledir) as jobfiles:
            for jobfile in jobfiles:
                jobfile = f"{jobfiledir}/{jobfile.name}"
                if not self._isfile(jobfile):
                    continue
                match = re.match(r'(.*/)([^/]+)$', jobfile)
                if match:
                    nfile = f"{tmpdir}/{match.group(2)}"
                    with open(jobfile, mode='r') as infile:
                        lines = [line.strip() for line in infile.readlines()]
                        with open(nfile, mode='w') as outfile:
                            for line in lines:
                                if re.match(r'filename\s*=\s*', line):
                                    print(f'{line}/{localid}/{localid}', file=outfile)
                                else:
                                    print(line, file=outfile)
                    new_jobfiles.append(nfile)
        self._timestamp(f"get_jobfiles({jobfiledir}) => {' '.join(new_jobfiles)}")
        return new_jobfiles

    def runit(self, process: int):
        localid = self._idname(separator='-')
        localrundir = f"{self.rundir}/{localid}"
        tmp_jobsfiledir = f"/tmp/fio-{localid}.job"
        os.makedirs(tmp_jobsfiledir)
        os.makedirs(localrundir)
        os.chdir(localrundir)
        jobfiles = self.get_jobfiles(self.jobfilesdir, tmp_jobsfiledir, localid)
        if not jobfiles:
            raise Exception("Error: no jobfiles provided!")
        for jobfile in jobfiles:
            self.runone(jobfile)
        shutil.rmtree(self.rundir, ignore_errors=True)


fio_client().run_workload()
