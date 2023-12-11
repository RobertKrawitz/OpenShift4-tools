# Clusterbuster release CI profile

force-pull=1

# instances : directories : files : blocksize : filesize : O_DIRECT
files-params=1:256:256:4096:0:0
files-params=1:256:256:4096:0:1
files-params=1:256:256:4096:4096:0
files-params=1:256:256:4096:4096:1
files-params=1:256:256:4096:262144:0
files-params=1:256:256:4096:262144:1
files-params=1:256:256:65536:262144:0
files-params=1:256:256:65536:262144:1
files-params=4:256:256:4096:0:0
files-params=4:256:256:4096:0:1
files-params=4:256:256:4096:4096:0
files-params=4:256:256:4096:4096:1
files-params=4:256:256:4096:262144:0
files-params=4:256:256:4096:262144:1
files-params=4:256:256:65536:262144:0
files-params=4:256:256:65536:262144:1
files-timeout=7200

fio-fdatasync=0
fio-timeout=5400
fio-absolute-filesize=128Gi
fio-memsize=4096

uperf-timeout=300

cpusoaker-timeout=600
cpusoaker-initial-replicas=1,2,3,4

job_runtime=60
artifactdir=
virtiofsd-direct=1
restart=0
use-python-venv=1
cleanup=1
deployment-type=replicaset

volume:files,fio:!vm=:emptydir:/var/tmp/clusterbuster
volume:files:vm=test-pvc:pvc:/var/tmp/clusterbuster:size=auto:inodes=auto
volume:fio:vm=test-pvc:pvc:/var/tmp/clusterbuster:size=auto
