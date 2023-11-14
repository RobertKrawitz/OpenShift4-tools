#!/bin/bash

# To run this from clusterbuster:
# clusterbuster --processes=8 -P byo cpusoaker-byo.sh 30

if [[ ${1:-} = --setup ]] ; then exit; fi

declare -i runtime=${1:-60}
declare -i iterations=0
declare -i loops_per_iteration=1000

# If you want to drop cache, you can use this.
# Your clusterbuster command line must use
# --byo-drop-cache=1
# for this to work.
#drop-cache

# If you want to synchronize your workload
#do-sync

cat 1>&2 <<EOF
My namespace is ${CB_NAMESPACE:-unknown}
My container is ${CB_CONTAINER:-unknown}
My pod is ${CB_PODNAME:-$(hostname)}
My pod is ${CB_ID:-unknown}
EOF

declare -i start_time=0
start_time=$(date +%s)

while ((runtime < 0 || $(date +%s) - start_time < runtime)) ; do
    for ((i = 0; i < loops_per_iteration; i++)) ; do:; done
    iterations=$((iterations + loops_per_iteration))
done

cat <<EOF
{
  "work_iterations": $iterations
}
EOF
