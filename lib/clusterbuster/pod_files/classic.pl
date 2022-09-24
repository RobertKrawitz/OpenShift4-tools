#!/usr/bin/perl

use POSIX;
use strict;
require "clientlib.pl";

my ($sleep_time, $processes) = parse_command_line(@ARGV);
initialize_timing();

sub runit() {
    my $pass = 0;
    my $ex = 0;
    my $ex2 = 0;
    my ($cfail) = 0;
    my ($refused) = 0;
    my $time_overhead = 0;
    $SIG{TERM} = sub { POSIX::_exit(0); };

    timestamp("Clusterbuster pod starting");
    my ($data_start_time) = xtime();
    if ($sleep_time > 0) {
	usleep($sleep_time * 1000000);
    }

    my ($data_end_time) = xtime();
    my ($elapsed_time) = $data_end_time - $data_start_time;
    my ($user, $sys, $cuser, $csys) = times;
    report_results($data_start_time, $data_end_time,
		   $data_end_time - $data_start_time,
		   $user, $sys);
}
run_workload(\&runit, $processes);
