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

my ($namespace, $container, $basetime, $baseoffset, $crtime, $processes, $exit_at_end, $synchost, $syncport, $sync_count, $sync_cluster_count, $sync_sleep) = @ARGV;
my ($start_time) = xtime();

$SIG{TERM} = sub() { docleanup() };
$basetime += $baseoffset;
$crtime += $baseoffset;

my ($pod) = hostname;

sub runit() {
    initialize_timing($basetime, $crtime, $synchost, $syncport, "$namespace:$pod:$container", $start_time);
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
				     $data_end_time, $data_end_time - $data_start_time,
				     $ucpu1, $scpu1);
    if ($syncport) {
	do_sync($synchost, $syncport, $results);
    }
}
my (%pids) = ();
for (my $i = 0; $i < $processes; $i++) {
    my $child;
    if (($child = fork()) == 0) {
	runit();
	exit(0);
    } else {
	$pids{$child} = 1;
    }
}
while (%pids) {
    my ($child) = wait();
    if ($child == -1) {
	finish($exit_at_end);
    } elsif (defined $pids{$child}) {
	if ($?) {
	    timestamp("Pid $child returned status $?!");
	    finish($exit_at_end, $?, $namespace, $pod, $container, $synchost, $syncport, $child);
	}
	delete $pids{$child};
    }
}

finish($exit_at_end);
