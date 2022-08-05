# Clusterbuster smoke test profile

# instances : directories : files : blocksize : filesize : O_DIRECT
files-params=1:32:32:4096:4096:0
files-timeout=1800

job_runtime=45

fio-fdatasync=0
fio-patterns=read
fio-iodepths=1
fio-ioengines=libaio
fio-ninst=1
fio-absolute-filesize=8Gi
fio-timeout=3600
fio-memsize=4096
fio-blocksize=1048576

uperf_runtime=30
uperf-msg-sizes=8192
uperf-nthr=1
uperf-ninst=1
uperf-timeout=300

cpusoaker-timeout=300
cpusoaker-replica-increment=10
cpusoaker-max-replicas=10

artifactdir=
virtiofsd-direct=1
use-python-venv=1
cleanup=1
restart=0
