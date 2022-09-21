#!/usr/bin/perl

use POSIX;
use strict;
my ($dir) = $ENV{'BAK_CONFIGMAP'};
require "$dir/clientlib.pl";

my ($processes, $runtime) = parse_command_line(@ARGV);
initialize_timing();

sub runit() {
    $SIG{TERM} = sub { kill 'KILL', -1; POSIX::_exit(0); };
    my ($iterations) = 0;
    my ($loops_per_iteration) = 10000;
    my ($firsttime) = 1;
    my ($avgcpu) = 0;
    my ($weight) = .25;
    my ($icputime);
    my ($interval) = 5;

    my ($data_start_time) = xtime();
    my ($user, $sys) = cputimes();
    my ($scputime) = $user + $sys;
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
    my ($user, $sys) = cputimes($user, $sys);
    my (%extra) = (
	'work_iterations' => $iterations
	);
    my ($elapsed_time) = $data_end_time - $data_start_time;
    report_results($data_start_time, $data_end_time, $elapsed_time, $user, $sys, \%extra);
}

run_workload(\&runit, $processes);
