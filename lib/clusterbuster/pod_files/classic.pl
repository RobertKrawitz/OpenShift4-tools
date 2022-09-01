#!/usr/bin/perl

use POSIX;
use strict;
my ($dir) = $ENV{'BAK_CONFIGMAP'};
require "$dir/clientlib.pl";

my ($sleep_time) = parse_command_line(@ARGV);

$SIG{TERM} = sub { POSIX::_exit(0); };

sub runit() {
    my $pass = 0;
    my $ex = 0;
    my $ex2 = 0;
    my ($cfail) = 0;
    my ($refused) = 0;
    my $time_overhead = 0;
    initialize_timing();

    timestamp("Clusterbuster pod starting");
    my ($data_start_time) = xtime();
    if ($sleep_time > 0) {
	usleep($sleep_time * 1000000);
    }

    my ($data_end_time) = xtime();
    my ($elapsed_time) = $data_end_time - $data_start_time;
    my ($user, $sys, $cuser, $csys) = times;
    my ($results) = print_json_report($data_start_time, $data_end_time,
				      $data_end_time - $data_start_time,
				      $user, $sys);
    timestamp("RESULTS $results");
    do_sync($results);
}
run_workload(1, \&runit);
