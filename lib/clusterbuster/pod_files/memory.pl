#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday usleep);
use Sys::Hostname;
use File::Basename;
my ($dir) = $ENV{'BAK_CONFIGMAP'};
require "$dir/clientlib.pl";

our ($namespace, $container, $basetime, $baseoffset, $crtime, $exit_at_end, $synchost, $syncport, $loghost, $logport, $processes, $memory, $runtime) = @ARGV;
my ($start_time) = xtime();
$SIG{TERM} = sub { kill 'KILL', -1; POSIX::_exit(0); };
$basetime += $baseoffset;
$crtime += $baseoffset;

sub runit() {
    my ($pod) = hostname;
    initialize_timing($basetime, $crtime, $synchost, $syncport, "$namespace:$pod:$container:$$", $start_time);
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
    my ($ucpu0, $scpu0) = cputime();
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
    my ($ucpu1, $scpu1) = cputime();
    $ucpu1 -= $ucpu0;
    $scpu1 -= $scpu0;
    my ($answer) = print_json_report($namespace, $pod, $container, $$, $data_start_time,
				     $data_end_time, $elapsed_time, $ucpu1, $scpu1);
    do_sync($synchost, $syncport, $answer);
    if ($logport > 0) {
	do_sync($loghost, $logport, $answer);
    }
}
$SIG{CHLD} = 'IGNORE';
if ($processes > 1) {
    for (my $i = 0; $i < $processes; $i++) {
        if ((my $child = fork()) == 0) {
            runit();
            exit(0);
        }
    }
} else {
    runit();
}

finish($exit_at_end);
