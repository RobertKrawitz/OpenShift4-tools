#!/bin/bash

# Copyright 2020 Robert Krawitz/Red Hat
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

# Bootstrap a command to run with bench-army-knife.  Used to start
# the agent and controller.

exec 1>&2
if (($# < 1)) ; then
    echo "Usage: $0 payload <args>"
    exit 1
fi

set -eu

# The payload may not be executable, and it may be in a read-only
# filesystem.  So move it to somewhere safe.
declare payload=$1
shift
export BAK_CONFIGMAP=${payload%/*}
export BAK_INSDIR=/var/tmp
declare inplace="$BAK_INSDIR/${payload##*/}"

if [[ -f "$payload" ]] ; then
    cp "$payload" "$inplace"
    chmod +x "$inplace"
else
    echo "Can't find $payload!" 1>&2
fi

echo "*** Bootstrap running payload: $inplace $*"

exec "$inplace" "$@"
