# Clusterbuster performance CI profile

force-pull=1

# instances : directories : files : blocksize : filesize : O_DIRECT
files-params=1:64:64:4096:4096:0
files-params=1:64:64:4096:4096:1
files-params=1:64:64:65536:262144:0
files-params=1:64:64:65536:262144:1
files-timeout=1800

job_runtime=60

fio-fdatasync=0
fio-patterns=read,write,randread,randwrite
fio-iodepths=1,4
fio-ioengines=libaio
fio-ninst=1,4
fio-absolute-filesize=128Gi
fio-timeout=3600
fio-memsize=4096

uperf-msg-sizes=64,1024,8192
uperf-nthr=4
uperf-ninst=1,4
uperf-timeout=300

cpusoaker-timeout=600
cpusoaker-replica-increment=20

artifactdir=
virtiofsd-direct=1
use-python-venv=1
cleanup=1
restart=0
deployment-type=replicaset
