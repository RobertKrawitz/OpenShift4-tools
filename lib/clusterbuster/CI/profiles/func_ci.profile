# Clusterbuster functional CI profile

# instances : directories : files : blocksize : filesize : O_DIRECT
files-params=1:64:64:4096:4096:0
files-params=1:64:64:65536:262144:1
files-timeout=1800

job_runtime=60

fio-fdatasync=0
fio-patterns=read,write,randread,randwrite
fio-iodepths=1
fio-ioengines=libaio
fio-ninst=1
fio-absolute-filesize=32Gi
fio-timeout=3600
fio-memsize=4096

uperf-msg-sizes=64,8192
uperf-nthr=1
uperf-ninst=1
uperf-timeout=300

cpusoaker-timeout=300
cpusoaker-replica-increment=10
cpusoaker-max-replicas=30
cpusoaker-workload=perl

artifactdir=
virtiofsd-direct=1
use-python-venv=1
cleanup=1
restart=0
deployment-type=replicaset
