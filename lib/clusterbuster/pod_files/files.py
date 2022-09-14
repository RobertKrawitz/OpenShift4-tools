#!/usr/bin/env python3

import sys
import os
import time
import subprocess
import mmap

if 'BAK_CONFIGMAP' in os.environ:
    sys.path.insert(0, os.environ['BAK_CONFIGMAP'])
from clusterbuster_pod_client import clusterbuster_pod_client

dir_list = ['/tmp']
client = clusterbuster_pod_client()
dirs, files_per_dir, blocksize, block_count, processes, o_direct, drop_cache_service, drop_cache_port = client.command_line()
if len(client.command_line()) > 8:
    dir_list = client.command_line()[8:]
dirs = int(dirs)
files_per_dir = int(files_per_dir)
blocksize = int(blocksize)
block_count = int(block_count)
processes = int(processes)
p_direct = clusterbuster_pod_client.toBool(o_direct)
drop_cache_port = int(drop_cache_port)
container = client.container()

flags = 0
if o_direct:
    flags = os.O_DIRECT


def remdir(dirname: str, oktofail: bool = False):
    try:
        os.rmdir(dirname)
    except Exception as err:
        if oktofail:
            subprocess.run(['rm', '-rf', dirname])
        else:
            raise err


def makethem(client: clusterbuster_pod_client, pid: int):
    buf = mmap.mmap(-1, blocksize)
    buf.write(('a' * blocksize).encode())
    ops = 0
    try:
        for bdir in dir_list:
            direc = f"{bdir}/p{pid}/{container}"
            os.makedirs(direc)
            ops = ops + 2
            for subdir in range(dirs):
                dirname = f"{direc}/{subdir}"
                os.mkdir(dirname)
                ops = ops + 1
                for fileidx in range(files_per_dir):
                    filename = f"{dirname}/{fileidx}"
                    fd = os.open(filename, flags | os.O_WRONLY | os.O_CREAT)
                    ops = ops + 1
                    for block in range(block_count):
                        answer = os.write(fd, buf)
                        if answer != blocksize:
                            raise os.IOError(f"Incomplete write to {filename}: {answer} bytes, expect {blocksize}")
                        ops = ops + 1
                    os.close(fd)
        return ops
    except Exception as err:
        client.timestamp(f"I/O error while creaating files: {err}")
        os._exit(1)


def readthem(client: clusterbuster_pod_client, pid: int, oktofail: bool = False):
    ops = 0
    try:
        for bdir in dir_list:
            direc = f"{bdir}/p{pid}/{container}"
            ops = ops + 2
            for subdir in range(dirs):
                dirname = f"{direc}/{subdir}"
                ops = ops + 1
                for fileidx in range(files_per_dir):
                    filename = f"{dirname}/{fileidx}"
                    try:
                        fd = os.open(filename, flags | os.O_RDONLY)
                        ops = ops + 1
                        for block in range(block_count):
                            with mmap.mmap(fd, blocksize, offset=block * blocksize, access=mmap.ACCESS_READ) as mm:
                                mm.read(blocksize)
                            ops = ops + 1
                        os.close(fd)
                    except Exception as exc:
                        if not oktofail:
                            raise exc
        return ops
    except Exception as err:
        client.timestamp(f"I/O error while reading files: {err}")
        os._exit(1)


def removethem(client: clusterbuster_pod_client, pid: int, oktofail: bool = False):
    def isdir(path: str):
        try:
            s = os.stat(path)
            return os.S_ISDIR(s.st_mode)
        except Exception:
            return False

    def isfile(path: str):
        try:
            s = os.stat(path)
            return os.S_ISREG(s.st_mode)
        except Exception:
            return False

    ops = 0
    try:
        for bdir in dir_list:
            pdir = f"{bdir}/p{pid}"
            if oktofail and not isdir(pdir):
                continue
            direc = f"{pdir}/{container}"
            if oktofail and not isdir(bdir):
                continue
            for subdir in range(dirs):
                dirname = f"{direc}/{subdir}"
                if oktofail and not isdir(subdir):
                    continue
                for fileidx in range(files_per_dir):
                    filename = f"{dirname}/{fileidx}"
                    if oktofail and not isfile(filename):
                        continue
                    os.unlink(filename)
                    ops = ops + 1
                remdir(dirname, oktofail)
                ops = ops + 1
            remdir(direc, oktofail)
            ops = ops + 1
            remdir(pdir, oktofail)
            ops = ops + 1
        return ops
    except Exception as err:
        client.timestamp(f"I/O error while removing files: {err}")
        os._exit(1)


def run_one_operation(client: clusterbuster_pod_client, op_name0: str, op_name1: str, op_name2: str, op_func, pid: int, data_start_time: float):
    client.sync_to_controller(client.idname([pid, f"start {op_name2}"]))
    client.drop_cache(drop_cache_service, drop_cache_port)
    ucpu0, scpu0 = client.cputimes()
    op_start_time = client.adjusted_time() - data_start_time
    ops = op_func(client, pid)
    op_end_time_0 = client.adjusted_time() - data_start_time
    client.drop_cache(drop_cache_service, drop_cache_port)
    op_end_time = client.adjusted_time() - data_start_time
    op_elapsed_time = op_end_time - op_start_time
    op_elapsed_time_0 = op_end_time_0 - op_start_time
    ucpu1, scpu1 = client.cputimes()
    ucpu1 -= ucpu0
    scpu1 -= scpu0
    answer = {
        'operation_elapsed_time': op_elapsed_time,
        'user_cpu_time': ucpu1,
        'system_cpu_time': scpu1,
        'cpu_time': ucpu1 + scpu1,
        'operation_start': op_start_time,
        'operation_end': op_end_time,
        'operations': ops,
        'operations_per_second': ops / op_elapsed_time
        }
    if op_name2 == 'read':
        answer['total_files'] = files_per_dir * dirs * len(dir_list)
        answer['block_count'] = block_count
        answer['size'] = blocksize
        answer['data_size'] = blocksize * block_count * answer['total_files']
        answer['data_rate'] = answer['data_size'] / op_elapsed_time_0
    client.timestamp(f'{op_name1} files...')
    client.sync_to_controller(client.idname([pid, f'end {op_name2}']))
    return answer


def runit(client: clusterbuster_pod_client, process: int, *args):
    removethem(client, os.getpid(), True)
    data_start_time = client.adjusted_time()

    subprocess.run('sync')
    answer_create = run_one_operation(client, 'Creating', 'Created', 'create', makethem, os.getpid(), data_start_time)
    client.timestamp("Sleeping for 60 seconds")
    time.sleep(60)
    client.timestamp('Back from sleep')
    answer_read = run_one_operation(client, 'Reading', 'Read', 'read', readthem, os.getpid(), data_start_time)
    client.timestamp("Sleeping for 60 seconds")
    time.sleep(60)
    client.timestamp('Back from sleep')
    answer_remove = run_one_operation(client, 'Removing', 'Remove', 'remove', removethem, os.getpid(), data_start_time)
    create_et = answer_create['operation_end'] - answer_create['operation_start']
    read_et = answer_read['operation_end'] - answer_read['operation_start']
    remove_et = answer_remove['operation_end'] - answer_remove['operation_start']
    data_start_time = answer_create['operation_start']
    data_end_time = answer_remove['operation_end']
    user_cpu = answer_create['user_cpu_time'] + answer_remove['user_cpu_time']
    system_cpu = answer_create['system_cpu_time'] + answer_remove['system_cpu_time']
    extras = {
        'summary': {
            'volumes': len(dir_list),
            'dirs_per_volume': dirs,
            'total_dirs': dirs * len(dir_list),
            'files_per_dir': files_per_dir,
            'total_files': files_per_dir * dirs * len(dir_list),
            'blocksize': blocksize,
            'blocks_per_file': block_count,
            'filesize': blocksize * block_count,
            'data_size': blocksize * block_count * files_per_dir * dirs * len(dir_list)
            },
        'create': answer_create,
        'read': answer_read,
        'remove': answer_remove
        }
    client.report_results(data_start_time, data_end_time, create_et + remove_et, user_cpu, system_cpu, extras)

client.run_workload(runit, processes)
