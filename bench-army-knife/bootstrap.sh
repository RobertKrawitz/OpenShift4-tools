#!/bin/bash

exec 1>&2
if (($# < 1)) ; then
    echo "Usage: $0 payload <args>"
    exit 1
fi

set -e
set -u

declare payload=$1
shift
export APPRENTICE_CONFIGMAP=${payload%/*}
export APPRENTICE_INSDIR=/opt/tool-apprentice
declare inplace="$APPRENTICE_INSDIR/${payload##*/}"

if [[ -f "$payload" ]] ; then
    cp "$payload" "$inplace"
    chmod +x "$inplace"
else
    echo "Can't find $payload!" 1>&2
fi

exec "$inplace" "$@"
