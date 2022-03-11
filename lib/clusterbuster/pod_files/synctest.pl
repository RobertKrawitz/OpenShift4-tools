#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday usleep);
use File::Path qw(make_path remove_tree);
use Sys::Hostname;
use File::Basename;
my ($dir) = $ENV{'BAK_CONFIGMAP'};
require "$dir/clientlib.pl";

our ($namespace, $container, $basetime, $baseoffset, $crtime, $processes, $exit_at_end, $synchost, $syncport, $loghost, $logport, $sync_count, $sync_cluster_count, $sync_sleep) = @ARGV;

$SIG{TERM} = sub() { docleanup() };
$basetime += $baseoffset;
$crtime += $baseoffset;

my ($pod) = hostname;

sub runit() {
    initialize_timing($basetime, $crtime, $synchost, $syncport, "$namespace:$pod:$container");
    my ($data_start_time) = xtime();
    my ($ucpu0, $scpu0) = cputime();
    foreach my $i (1..$sync_count) {
	foreach my $j (1..$sync_cluster_count) {
	    do_sync($synchost, $syncport, "$namespace:$pod:$container:$$:$i:$j");
	}
	if ($sync_sleep > 1) {
	    usleep($sync_sleep * 1000000);
	}
    }
    my ($ucpu1, $scpu1) = cputime();
    $ucpu1 -= $ucpu0;
    $scpu1 -= $scpu0;

    my ($data_end_time) = xtime();
    my ($results) = print_json_report($namespace, $pod, $container, $$, $data_start_time,
				     $data_end_time, $data_start_time - $data_end_time,
				     $ucpu1, $scpu1);
    if ($syncport) {
	do_sync($synchost, $syncport, $results);
    }
    if ($logport > 0) {
	do_sync($loghost, $logport, $results);
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
