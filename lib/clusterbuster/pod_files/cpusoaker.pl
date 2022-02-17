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

our ($namespace, $container, $basetime, $baseoffset, $poddelay, $crtime, $exit_at_end, $synchost, $syncport, $loghost, $logport, $processes, $runtime) = @ARGV;
$SIG{TERM} = sub { kill 'KILL', -1; POSIX::_exit(0); };
$basetime += $baseoffset;
$crtime += $baseoffset;

my ($start_time) = xtime();
my ($pod) = hostname;

sub runit() {
    my ($iterations) = 0;
    my ($loops_per_iteration) = 10000;
    my ($firsttime) = 1;
    my ($avgcpu) = 0;
    my ($weight) = .25;
    my ($icputime);
    my ($interval) = 5;

    my $delaytime = $basetime + $poddelay - $start_time;
    if ($delaytime > 0) {
	timestamp("Sleeping $delaytime seconds to synchronize");
	usleep($delaytime * 1000000);
    }
    do_sync($synchost, $syncport);
    my ($data_start_time) = xtime();
    my ($suser, $ssys, $scuser, $scsys) = times;
    my ($scputime) = cputime();
    my ($basecpu) = $scputime;
    my ($prevcpu) = $basecpu;
    my ($prevtime) = $start_time;
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
		my ($etime) = $ntime - $start_time;
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
    my ($fstring) = <<'EOF';
{
  "application": "clusterbuster-json",
  "namespace": "%s",
  "pod": "%s",
  "container": "%s",
  "process_id": %d,
  "pod_create_time_offset_from_base": %f,
  "pod_start_time_offset_from_base": %f,
  "data_start_time_offset_from_base": %f,
  "data_end_time_offset_from_base": %f,
  "data_elapsed_time": %f,
  "user_cpu_time": %f,
  "system_cpu_time": %f,
  "cpu_time": %f,
  "work_iterations": %d
}
EOF
    $fstring =~ s/[ \n]+//g;
    my ($elapsed_time) = $data_end_time - $data_start_time;
    my ($answer) = sprintf($fstring, $namespace, $pod, $container, $$, $crtime - $basetime,
			   $start_time - $basetime, $data_start_time - $basetime,
			   $data_end_time - $basetime, $elapsed_time, $user, $sys, $user + $sys,
			   $iterations);
    print STDERR "$answer\n";
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
print STDERR "FINIS\n";
if ($exit_at_end) {
    timestamp("About to exit");
    while (wait() > 0) {}
    timestamp("Done waiting");
    POSIX::_exit(0);
} else {
    timestamp("Waiting forever");
    pause()
}
