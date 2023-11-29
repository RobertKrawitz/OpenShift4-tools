#!/bin/bash

# Copyright 2022 Robert Krawitz/Red Hat
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

# Unfortunate that there's no way to tell shellcheck to always source
# specific files.
# shellcheck disable=SC2034

# Intended to be sourced by clients of the workload API

declare -Ag __registered_workloads__=()
declare -Ag __workload_aliases__=()
declare -Ag debug_conditions=()
shopt -s extdebug
export PIDS_TO_NOT_KILL="$$ $BASHPID"

function timestamp() {
    while IFS= read -r 'LINE' ; do
	printf "%s %s\n" "$(TZ=GMT-0 date '+%Y-%m-%dT%T.%N' | cut -c1-26)" "$LINE"
    done
}

function protect_pids() {
    debug protect_pids "Protected pids $PIDS_TO_NOT_KILL + $*"
    PIDS_TO_NOT_KILL+=" $*"
}

function register_debug_condition() {
    local error="$1"
    local condition
    local options
    IFS='=' read -r condition options <<< "$error"
    debug_conditions["$condition"]=${options:-SET}
    warn "*** Registering debug condition '$condition' = '${debug_conditions[$condition]}'"
}

function test_debug() {
    local condition=${1:-}
    [[ -n "$condition" && (-n "${debug_conditions[$condition]:-}" || -n "${debug_conditions[all]:-}") ]]
}

function debug() {
    local condition=${1:-}
    shift
    if test_debug "$condition" ; then
	echo "*** DEBUG $condition:" "${@@Q}" |timestamp 1>&2
    fi
    return 0
}

function bool() {
    local OPTIND=0
    local yes=1
    local no=0
    while getopts 'y:t:n:f:Y:T:' opt "$@" ; do
	case "$opt" in
	    y|t) yes="$OPTARG"	      ;;
	    n|f) no="$OPTARG"	      ;;
	    Y|T) yes="$OPTARG"; no='' ;;
	    *)               	      ;;
	esac
    done
    local value
    for value in "$@" ; do
	case "${value,,}" in
	    ''|1|y|yes|tru*) echo "$yes" ;;
	    *)               echo "$no"  ;;
	esac
    done
}

function parse_size() {
    # We cannot use getopts here because negative sizes would
    # look like options.
    local size
    local delimiter=$'\n'
    local -a answers=()
    local trailer=
    while [[ $1 = '-'[nd]* ]] ; do
	case "$1" in
	    -n) delimiter=' ' ;;
	    -d) shift; delimiter=$2; trailer=$'\n' ;;
	    -d*) delimiter=${1:2}; tralier=$'\n' ;;
	esac
	shift
    done
    local sizes=$*
    sizes=${sizes//,/ }
    for size in $sizes ; do
	if [[ $size =~ (-?[[:digit:]]+)([[:alpha:]]*) ]] ; then
	    local sizen=${BASH_REMATCH[1]}
	    local size_modifier=${BASH_REMATCH[2],,}
	    local -i size_multiplier=1
	    case "$size_modifier" in
		''|b)             size_multiplier=1              ;;
		k|kb|kilobytes)   size_multiplier=1000           ;;
		ki|kib|kibibytes) size_multiplier=1024           ;;
		m|mb|megabytes)   size_multiplier=1000000        ;;
		mi|mib|mebibytes) size_multiplier=1048576        ;;
		g|gb|gigabytes)   size_multiplier=1000000000     ;;
		gi|gib|gibibytes) size_multiplier=1073741824     ;;
		t|tb|terabytes)   size_multiplier=1000000000000  ;;
		ti|tib|tebibytes) size_multiplier=1099511627776  ;;
		*) fatal "Cannot parse size $size"		 ;;
	    esac
	    answers+=("$((sizen*size_multiplier))")
	else
	    fatal "Cannot parse size $size"
	fi
    done
    (IFS=$delimiter; echo -n "${answers[*]}$trailer")
}

function parse_optvalues() {
    echoarg=
    if [[ $1 = '-n' ]] ; then
	echoarg=-n
	shift
    fi
    local args=$*
    args=${args//,/ }
    for arg in $args ; do
	echo $echoarg "$arg"
    done
}

function parse_option() {
    local option=$1
    option=${option## }
    option=${option%% }
    local optname
    local optvalue
    optname=${option%%=*}
    optname=${optname,,}
    optvalue=${option#*=}
    noptname=${optname//-/_}
    if [[ $option != *'='* ]] ; then
	if [[ $noptname = "no_"* || $optname = "dont_"* || $noptname = "no-"* || $optname = "dont-"* ]] ; then
	    noptname=${noptname#dont_}
	    noptname=${noptname#no_}
	    noptname=${noptname#dont-}
	    noptname=${noptname#no-}
	    optvalue=0
	else
	    optvalue=1
	fi
    fi
    local noptname1=${noptname//_/}
    echo "$noptname1 $noptname $optvalue"
}

function _help_options_workloads() {
    local workload
    while read -r workload ; do
	if [[ -z "$workload" ]] ; then
	    continue
	fi
	echo
	call_api -w "$workload" help_options
    done <<< "$(workloads_supporting_api help_options)"
}

function _document_workloads() {
    local workload
    while read -r workload ; do
	if [[ -z "$workload" ]] ; then
	    continue
	fi
	echo
	call_api -w "$workload" document
    done <<< "$(workloads_supporting_api document)"
}

function load_workloads() {
    local -a path=$1
    local -a subdir=${2:-}
    local -a workloads
    readarray -t workloads <<< "$(find_files_on_path "${subdir}/workloads" "*.workload" "$path")"
    local dir
    local workload
    for workload in "${workloads[@]}" ; do
	. "$workload" || fatal "Can't load workload $workload"
    done
}

function find_on_path() {
    local ftype=$1
    local fn=$2
    if [[ $fn = '/'* ]] ; then
	echo "$fn"
	return 0
    fi
    local path=${3:-$CB_LIBPATH}
    local -a xpath
    readarray -d : -t xpath <<< "$path"
    xpath=("${xpath[@]%$'\n'}")
    local d
    for d in "${xpath[@]}" ; do
	d=${d:-.}
	local l="${d}/${ftype}/${fn}"
	l=${l//\/\///}
	if [[ -f "$l" ]] ; then
	    echo "$l"
	    return 0
	fi
    done
    return 1
}

function find_files_on_path() {
    local ftype=${1:-}
    local pattern=${2:-*}
    local path=${3:-$CB_LIBPATH}
    local -a xpath
    readarray -d : -t xpath <<< "$path"
    xpath=("${xpath[@]%$'\n'}")
    local d
    for d in "${xpath[@]}" ; do
	d=${d:-.}
	local l="${d}/${ftype}"
	local f
	for f in "$l"/$pattern ; do
	    echo "${f//\/\///}"
	done
    done
    return 0
}

function dispatch_generic() {
    local -i probe_only=0
    if [[ $1 = '-p' ]] ; then
	probe_only=1
	shift
    fi
    local workload=$1
    local API=$2
    shift 2
    local funcname="${workload}_${API}"
    if type -t "$funcname" >/dev/null ; then
	((probe_only)) && return 0
	"$funcname" "$@"
    else
	return 1
    fi
}

function register_workload() {
    local OPTIND=0
    local OPTARG
    local workload_dispatch_function=dispatch_generic
    local arg
    while getopts 'd:' arg "$@" ; do
	case "$arg" in
	    d) workload_dispatch_function=$OPTARG ;;
	    *)                                    ;;
	esac
    done
    shift $((OPTIND-1))
    local workload_name=$1; shift
    if [[ ! $workload =~ [[:alpha:]][[:alnum:]_]+ ]] ; then
	fatal "Illegal workload name $workload"
    elif [[ -n "${__workload_aliases__[${workload_name,,}]:-}" ]] ; then
	warn "Attempting to re-register workload $workload_name"
	return
    elif ! type -t "$workload_dispatch_function" >/dev/null ; then
	fatal "Workload dispatch function $workload_dispatch_function not defined"
    fi
    __registered_workloads__[$workload_name]=$workload_dispatch_function
    __workload_aliases__[${workload_name,,}]=$workload_name
    local walias
    for walias in "$@" ; do
	if [[ -n "${__registered_workloads__[$walias]:-}" || -n "${__workload_aliases__[${walias,,}]:-}" ]] ; then
	    fatal "Attempting to register workload alias that already exists"
	fi
	__workload_aliases__[${walias,,}]=${workload_name}
    done
}

function supports_api() {
    local workload
    local OPTIND=0
    while getopts 'w:' opt "$@" ; do
	case "$opt" in
	    w) workload=$OPTARG ;;
	    *)			;;
	esac
    done
    shift $((OPTIND - 1))
    local api=$1
    [[ -z "$workload" ]] && return 1
    [[ -z "${__registered_workloads__[$workload]:-}" ]] && fatal "supports_api $workload $api: workload not known"
    "${__registered_workloads__[$workload]}" -p "$workload" "$api"
}

function workloads_supporting_api() {
    local api=$1
    local workload
    while read -r workload ; do
	supports_api -w "$workload" "$api" && echo "$workload"
    done <<< "$(print_workloads '')"
}

function _call_api() {
    local workload=
    local -a workloads=()
    local -i all=0
    local -i any_OK=0
    local -i safe=0
    local OPTIND=0
    while getopts 'w:saA' opt "$@" ; do
	case "$opt" in
	    w) workload=$OPTARG ;;
	    s) safe=1		;;
	    a) all=1		;;
	    A) any_OK=1		;;
	    *)			;;
	esac
    done
    local -i status=$any_OK
    shift $((OPTIND - 1))
    local api=${1:-}
    [[ -z "$api" ]] && fatal "call_api [-w workload|-a] [-A] API args..."
    [[ -n "$workload" ]] && workloads+=("$workload")
    if ((all)) ; then
	local lworkload
	for lworkload in "${!__registered_workloads__[@]}" ; do
	    [[ $lworkload != "$workload" ]] && workloads+=("$lworkload")
	done
    fi
    [[ -z "${workloads[*]}" ]] && fatal "call_api $api does not have a workload specified!"
    for workload in "${workloads[@]}" ; do
	if supports_api -w "$workload" "$api" ; then
	    "${__registered_workloads__[$workload]}" "$workload" "$@"
	    local -i my_status=$?
	    if ((any_OK && my_status == 0)) ; then
		status=0
	    elif ((! any_OK && my_status > 0)) ; then
		status=1
	    fi
	elif ((!safe && !any_OK)) ; then
	    status=1
	fi
    done
    return $status
}

function call_api() {
    debug call_api "$@"
    _call_api "$@"
    local _status=$?
    debug call_api "$@" "< $_status"
    return $_status
}

function print_workloads() {
    local prefix="${1:-}"
    local workloads
    while read -r workload ; do
	echo "$prefix$workload"
    done <<< "$(IFS=$'\n'; echo "${!__registered_workloads__[*]}" |sort)"
}

function get_workload() {
    local requested_workload="$1"
    if [[ -n "${__workload_aliases__[${requested_workload,,}]:-}" ]] ; then
	echo "${__workload_aliases__[${requested_workload,,}]:-}"
    else
	return 1
    fi
}
function mk_num_list() {
    echo "[$(IFS=','; echo "$*")]"
}

function mk_str_list() {
    local _strings=()
    local _arg
    for _arg in "$@" ; do
	_strings+=("\"$_arg\"")
    done
    echo "[$(IFS=','; echo "${_strings[*]}")]"
}

# Based on https://gist.github.com/akostadinov/33bb2606afe1b334169dfbf202991d36
function stack_trace() {
    local -a stack=()
    local stack_size=${#FUNCNAME[@]}
    local -i start=${1:-1}
    local -i max_frames=${2:-$stack_size}
    ((max_frames > stack_size)) && max_frames=$stack_size
    local -i i
    local -i max_funcname=0
    local -i stack_size_len=${#max_frames}
    local -i max_filename_len=0
    local -i max_line_len=0

    # to avoid noise we start with 1 to skip the stack function
    for (( i = start; i < max_frames; i++ )); do
	local func="${FUNCNAME[$i]:-(top level)}"
	((${#func} > max_funcname)) && max_funcname=${#func}
	local src="${BASH_SOURCE[$i]:-(no file)}"
	# Line number is used as a string here, not an int,
	# since we want the length of it as a string.
	local line="${BASH_LINENO[$(( i - 1 ))]}"
	[[ $src = "${__realsc__:-}" ]] && src="${__topsc__:-}"
	((${#src} > max_filename_len)) && max_filename_len=${#src}
	((${#line} > max_line_len)) && max_line_len=${#line}
    done
    local stack_frame_str="    (%${stack_size_len}d)   %${max_filename_len}s:%-${max_line_len}d  %${max_funcname}s%s"
    local -i arg_count=${BASH_ARGC[0]}
    for (( i = start; i < max_frames; i++ )); do
	local func="${FUNCNAME[$i]:-(top level)}"
	local -i line="${BASH_LINENO[$(( i - 1 ))]}"
	local src="${BASH_SOURCE[$i]:-(no file)}"
	[[ $src = "${__realsc__:-}" ]] && src="${__topsc__:-}"
	local -i frame_arg_count=${BASH_ARGC[$i]}
	local argstr=
	if ((frame_arg_count > 0)) ; then
	    local -i j
	    for ((j = arg_count + frame_arg_count - 1; j >= arg_count; j--)) ; do
		argstr+=" ${BASH_ARGV[$j]}"
	    done
	fi
	# We need a dynamically generated string to get the columns correct.
	# shellcheck disable=SC2059
	stack+=("$(printf "$stack_frame_str" "$((i - start))" "$src" "$line" "$func" "${argstr:+ $argstr}")")
	arg_count=$((arg_count + frame_arg_count))
    done
    (IFS=$'\n'; echo "${stack[*]}")
}

# The big red button if something goes wrong.

function childrenof() {
    IFS=' '
    function is_descendent() {
	local -i child=$1
	local ancestor=$2
	if ((child == ancestor)) ; then
	    true
	else
	    parent=${ps_parents[$child]:-1}
	    case "$parent" in
		1)           false ;;
		"$ancestor") true  ;;
		*)           is_descendent "$parent" "$ancestor" ;;
	    esac
	fi
    }
    local -A exclude=()
    local OPTARG
    local OPTIND=0
    while getopts 'e:' opt "$@" ; do
	case "$opt" in
	    e) exclude[$OPTARG]=1 ;;
	    *)                    ;;
	esac
    done
    if [[ -n "$PIDS_TO_NOT_KILL" ]] ; then
	debug protect_pids "killthemall will not kill $PIDS_TO_NOT_KILL"
	local pid
	for pid in $PIDS_TO_NOT_KILL ; do
	    exclude[$pid]=1
	done
    fi
    shift $((OPTIND-1))
    local target=$1
    local -A ps_parents=()
    local -A ps_commands=()
    local ppid
    local pid
    local command
    local ignore
    while read -r pid ppid command ignore; do
	ps_parents["$pid"]=$ppid
	ps_commands["$pid"]=$command
    done <<< "$(ps -axo pid,ppid,command | tail -n +2)"
    for pid in "${!ps_parents[@]}" ; do
	# Don't kill loggers and the report generator; we still want
	# output even if there's a failure.
	if [[ -z "${!exclude[$pid]:-}" && "${ps_commands[$pid]}" != 'tee'* && "${ps_commands[$pid]}" != *'clusterbuster-report'* ]] ; then
	    if is_descendent "$pid" "$target" ; then
		debug protect_pids "   killing $pid"
		echo "$pid"
	    fi
	fi
    done
}

function killthemall() {
    local signal=TERM
    if [[ ${1:-} = '-'* ]] ; then
	signal=${1#-}
	shift
    fi
    echo "FATAL ERROR: ${*:-Exiting!}" 1>&2
    # Selectively kill all processes.  We don't want to kill
    # processes between us and the root, or processes that
    # aren't actually clusterbuster (e. g. reporting)
    # Also, RHEL 8 doesn't support kill -<pgrp> syntax
    local -a pids_to_kill=()
    readarray -t pids_to_kill <<< "$(childrenof -e "$BASHPID" $$)"
    # killthemall can livelock under the wrong circumstances.
    # Make sure that that doesn't happen; we want to control
    # our own exit.
    trap '' TERM
    if [[ -n "${pids_to_kill[*]}" ]] ; then
	/bin/kill -TERM "${pids_to_kill[@]}" >/dev/null 2>&1
	if (( $$ == BASHPID )) ; then
	    wait
	    local -i tstart
	    tstart=$(date +%s)
	    until [[ -z "$(ps -o pid "${pids_to_kill[@]}" | awk '{print $1}' | grep -v "^${$}$" | tail -n +2)" ]] ; do
		sleep 1
		if (( $(date +%s) - tstart > 60 )) ; then
		    warn "Unable to terminate all processes!"
		    ps "${pids_to_kill[@]}" 1>&2
		    break
		fi
	    done
	fi
    fi
    exit 1
}
