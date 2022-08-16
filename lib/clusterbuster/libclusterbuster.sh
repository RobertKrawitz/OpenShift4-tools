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
    local size
    echoarg=
    if [[ $1 = '-n' ]] ; then
	echoarg=-n
	shift
    fi
    local sizes=$*
    sizes=${sizes//,/ }
    for size in $sizes ; do
	if [[ $size =~ (-?[[:digit:]]+)([[:alpha:]]*) ]] ; then
	    local size=${BASH_REMATCH[1]}
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
		*) fatal "Cannot parse size $optvalue"           ;;
	    esac
	    echo $echoarg "$((size*size_multiplier)) "
	else
	    fatal "Cannot parse size $optvalue"
	fi
    done
}

function parse_option() {
    local option=$1
    option=${option## }
    option=${option%% }
    if [[ $option =~ ^([^=]+)\ *=\ *([^\ ].*)? ]] ; then
	option="${BASH_REMATCH[1]}=${BASH_REMATCH[2]}"
    fi
    [[ -n "$option" ]] || return
    local optname
    local optvalue
    optname=${option%%=*}
    optname=${optname,,}
    optvalue=${option#*=}
    noptname=${optname//-/_}
    if [[ $option != *'='* ]] ; then
	if [[ $noptname = "no_"* || $optname = "dont_"* ]] ; then
	    noptname=${noptname#dont_}
	    noptname=${noptname#no_}
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

function __split_path() {
    local workload_path=
    workload_path="$(IFS=:; echo "$*")"
    local IFS=:
    set -f
    # shellcheck disable=SC2206
    local -a dirlist=($workload_path)
    local dir
    for dir in "${dirlist[@]}" ; do
	echo "${dir:-.}"
    done
}

function load_workloads() {
    local -a workload_path
    readarray -t workload_path <<< "$(__split_path "$@")"
    local dir
    local workload
    for dir in "${workload_path[@]}" ; do
	for workload in "$dir"/*.workload ; do
	    . "$workload" || fatal "Can't load workload $workload"
	done
    done
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
    local workload_name=$1
    local workload_dispatch_function=$2
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
    shift 2
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

function call_api() {
    (( $# < 1 )) && fatal "call_api [-w workload|-a] [-A] API args..."
    local workload
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
    local api=$1
    if ((all)) ; then
	workloads=("${!__registered_workloads__[@]}")
    elif [[ -n "$workload" ]] ; then
	workloads=("$workload")
    else
	fatal "call_api $api does not have a workload specified!"
    fi
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
