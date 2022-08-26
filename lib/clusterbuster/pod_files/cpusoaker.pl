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

our ($namespace, $container, $basetime, $baseoffset, $crtime, $exit_at_end, $synchost, $syncport, $loghost, $logport, $processes, $runtime) = @ARGV;
my ($start_time) = xtime();
$SIG{TERM} = sub { kill 'KILL', -1; POSIX::_exit(0); };
$basetime += $baseoffset;
$crtime += $baseoffset;

sub runit() {
    my ($pod) = hostname;
    initialize_timing($basetime, $crtime, $synchost, $syncport, "$namespace:$pod:$container:$$", $start_time);
    my ($iterations) = 0;
    my ($loops_per_iteration) = 10000;
    my ($firsttime) = 1;
    my ($avgcpu) = 0;
    my ($weight) = .25;
    my ($icputime);
    my ($interval) = 5;

    my ($data_start_time) = xtime();
    my ($suser, $ssys, $scuser, $scsys) = times;
    my ($scputime) = cputime();
    my ($basecpu) = $scputime;
    my ($prevcpu) = $basecpu;
    my ($prevtime) = $data_start_time;
    while ($runtime < 0 || xtime() - $data_start_time < $runtime) {
        my ($a) = 1;
        for (my $i = 0; $i < $loops_per_iteration; $i++) {
            $a = $a + $a;
        }
        $iterations += $loops_per_iteration;
        if ($ENV{"VERBOSE"} > 0) {
	    my ($ntime) = xtime();
	    if ($ntime - $prevtime >= $interval) {
		my (@times) = times();
		my ($user, $system, $cuser, $csystem) = times();
		my ($etime) = $ntime - $data_start_time;
		my ($cpu) = cputime();
		my ($cputime) = $cpu - $basecpu;
		my ($icputime) = $cpu - $prevcpu;
		if ($firsttime) {
		    $avgcpu = $cputime;
		    $firsttime = 0;
		} else {
		    $avgcpu = ($icputime * $weight) + ($avgcpu * (1.0 - $weight));
		}
		$prevtime = $ntime;
		$prevcpu = $cpu;
            }
        }
    }
    my ($data_end_time) = xtime();
    my ($cputime) = cputime() - $scputime;
    my ($euser, $esys, $ecuser, $ecsys) = times;
    my ($user) = $euser - $suser;
    my ($sys) = $esys - $ssys;
    my (%extra) = (
	'work_iterations' => $iterations
	);
    my ($elapsed_time) = $data_end_time - $data_start_time;
    my ($answer) = print_json_report($namespace, $pod, $container, $$, $data_start_time,
				     $data_end_time, $elapsed_time, $user, $sys, \%extra);
    do_sync($synchost, $syncport, $answer);
    if ($logport > 0) {
	do_sync($loghost, $logport, $answer);
    }
}
my (%pids) = ();
if ($processes > 1) {
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
		finish($exit_at_end, $?)
	    }
	    delete $pids{$child};
	}
    }
} else {
    runit();
}

finish($exit_at_end);
