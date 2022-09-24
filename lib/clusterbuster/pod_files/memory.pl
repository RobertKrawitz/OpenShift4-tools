#!/usr/bin/perl

use POSIX;
use strict;
use File::Basename;
require "clientlib.pl";

my ($processes, $memory, $runtime) = parse_command_line(@ARGV);
initialize_timing();
$SIG{TERM} = sub { kill 'KILL', -1; POSIX::_exit(0); };

sub runit() {
    my ($mib_blk) = '';
    my ($kib_blk) = '';
    my ($leftover_blk) = '';
    my ($bigblocks) = $memory / 1048576;
    my ($smallblocks) = ($memory % 1048576) / 1024;
    my ($leftover) = $memory % 1024;
    my ($memory_blk) = '';

    if ($bigblocks || $smallblocks) {
	$kib_blk = 'a';
	foreach my $i (1..10) {
	    $kib_blk .= $kib_blk;
	}
	if ($bigblocks) {
	    $mib_blk = $kib_blk;
	    foreach my $i (1..10) {
		$mib_blk .= $mib_blk;
	    }
	}
    }
    if ($leftover) {
	foreach my $i (0..$leftover - 1) {
	    $leftover_blk .= 'b';
	}
    }
    my ($ptr) = 0;
    my ($ucpu, $scpu) = cputimes();
    my ($data_start_time) = xtime();
    if ($bigblocks) {
	foreach my $i (0..$bigblocks - 1) {
	    substr($memory_blk, $ptr, 1048576) = $mib_blk;
	    $ptr += 1048576;
	}
    }
    if ($smallblocks) {
	foreach my $i (0..$smallblocks - 1) {
	    substr($memory_blk, $ptr, 1024) = $kib_blk;
	    $ptr += 1024;
	}
    }
    if ($leftover) {
	substr($memory_blk, $ptr, $leftover) = $leftover_blk;
    }
    if ($runtime >= 0) {
	usleep($runtime * 1048576);
    } else {
	sleep();
    }
    my ($data_end_time) = xtime();
    my ($elapsed_time) = $data_end_time - $data_start_time;
    my ($ucpu, $scpu) = cputimes($ucpu, $scpu);
    report_results($data_start_time, $data_end_time, $elapsed_time, $ucpu, $scpu);
}
run_workload(\&runit, $processes);
