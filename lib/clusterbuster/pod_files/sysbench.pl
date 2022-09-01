#!/usr/bin/perl

use POSIX;
use strict;
use File::Path qw(make_path);
my ($dir) = $ENV{'BAK_CONFIGMAP'};
require "$dir/clientlib.pl";

my ($processes, $rundir, $runtime, $sysbench_generic_args, $sysbench_cmd, $sysbench_fileio_args, $sysbench_modes) = parse_command_line(@ARGV);

$SIG{TERM} = sub() { docleanup() };

initialize_timing();
my ($localrundir) = sprintf('%s/%s/%d', $rundir, podname(), $$);

sub removeRundir() {
    if (-d "$localrundir") {
	open(CLEANUP, "-|", "rm -rf '$localrundir'");
	while (<CLEANUP>) {
	    1;
	}
	close(CLEANUP);
    }
}

sub docleanup()  {
    print STDERR "CLEANUP\n";
    removeRundir();
    kill 'KILL', -1;
    POSIX::_exit(0);
}

my (%units_multiplier) = (
    'kb'  => 1000,
    'kib' => 1024,
    'mb'  => 1000 * 1000,
    'mib' => 1024 * 1024,
    'gb'  => 1000 * 1000 * 1000,
    'gib' => 1024 * 1024 * 1024,
    'tb'  => 1000 * 1000 * 1000 * 1000,
    'tib' => 1024 * 1024 * 1024 * 1024,
    );

sub runit() {
    my ($files) = 0;
    my ($totalbytes) = 0;
    my ($seconds) = 0;
    my ($rate) = 0;
    my ($et) = 0;
    my (@known_sysbench_fileio_modes) = qw(seqwr seqrewr seqrd rndrd rndwr rndrw);
    my ($iterations) = 0;
    my ($loops_per_iteration) = 10000;
    if ($sysbench_modes) {
        @known_sysbench_fileio_modes = split(/ +/, $sysbench_modes);
    }
    timestamp(join("|", @known_sysbench_fileio_modes));
    removeRundir();
    if (! make_path($localrundir)) {
        timestamp("Cannot create run directory $localrundir: $!");
	exit(1);
    }
    if (! chdir($localrundir)) {
        timestamp("Cannot cd $localrundir: $!");
	exit(1);
    }
    my (%op_answers) = ();
    my ($firsttime) = 1;
    my ($avgcpu) = 0;
    my ($weight) = .25;
    my ($icputime);
    my ($interval) = 5;
    my $data_start_time = xtime();

    my ($base0_user, $base0_sys) = cputime();
    foreach my $mode (@known_sysbench_fileio_modes) {
	do_sync(idname("$mode+prepare"));
	timestamp("Preparing...");
	timestamp("sysbench --time=$runtime $sysbench_generic_args $sysbench_cmd prepare --file-test-mode=$mode $sysbench_fileio_args");
	open(PREPARE, "-|", "sysbench --time=$runtime $sysbench_generic_args $sysbench_cmd prepare --file-test-mode=$mode $sysbench_fileio_args") || die "Can't run sysbench: $!\n";
	while (<PREPARE>) {
	    if ($_ =~ /^([[:digit:]]+) bytes written in ([[:digit:].]+) seconds/) {
		$totalbytes = $1;
		$seconds = $2;
		$rate = $1 / $2;
	    } elsif ($_ =~ /^Creating file /) {
		$files++;
		next;
	    }
	    if ($ENV{"VERBOSE"} > 0) {
		chomp;
		timestamp($_);
	    }
	}
	close PREPARE;

	do_sync(idname("$mode+start"));
	my ($op0_user, $op0_sys) = cputime();
	timestamp("Running...");
	timestamp("sysbench --time=$runtime $sysbench_generic_args $sysbench_cmd run --file-test-mode=$mode $sysbench_fileio_args");
	open(RUN, "-|", "sysbench --time=$runtime $sysbench_generic_args $sysbench_cmd run --file-test-mode=$mode $sysbench_fileio_args") || die "Can't run sysbench: $!\n";
	my (%op_answer) = (
	    'final_fsync_enabled' => 'Disabled',
	    'io_mode' => 'unknown',
	    'rdwr_ratio' => 1.0,
	    );
	while (<RUN>) {
	    if      ($_ =~ m;^[[:space:]]*([[:digit:]]+) *files, *([[:digit:]]+)([KMGT]i?B);) {
		$op_answer{'files'} = $1 + 0.0;
		$op_answer{'filesize'} = $2 * (defined $units_multiplier{lc $3} ? $units_multiplier{lc $3} : 1);
	    } elsif ($_ =~ m;^[[:space:]]*Block size *([[:digit:]]+)([KMGT]i?B);) {
		$op_answer{'blocksize'} = $1 * (defined $units_multiplier{lc $2} ? $units_multiplier{lc $2} : 1);
	    } elsif ($_ =~ m;^[[:space:]]*Read/Write ratio for combined random IO test: *([[:digit:]]+(\.[[:digit:]]+)?);) {
		$op_answer{'rdwr_ratio'} = $1 * 1.0;
	    } elsif ($_ =~ m;^[[:space:]]*Periodic FSYNC enabled, calling fsync\(\) each ([[:digit:]]+);) {
		$op_answer{'fsync_frequency'} = $1 + 0.0;
	    } elsif ($_ =~ m;^[[:space:]]*calling fsync\(\) at the end of test, (enabled|disabled);i) {
		$op_answer{'final_fsync_enabled'} = $1 + 0.0;
	    } elsif ($_ =~ m;^[[:space:]]*Using (.*) I/O mode;) {
		$op_answer{'io_mode'} = $1 + 0.0;
	    } elsif ($_ =~ m;^[[:space:]]*reads/s:[[:space:]]*([[:digit:].]+);) {
		$op_answer{'read_ops'} = $1 + 0.0;
	    } elsif ($_ =~ m;^[[:space:]]*writes/s:[[:space:]]*([[:digit:].]+);) {
		$op_answer{'write_ops'} = $1 + 0.0;
	    } elsif ($_ =~ m;^[[:space:]]*fsyncs/s:[[:space:]]*([[:digit:].]+);) {
		$op_answer{'fsync_ops'} = $1 + 0.0;
	    } elsif ($_ =~ m;^[[:space:]]*read, MiB/s:[[:space:]]*([[:digit:].]+);) {
		$op_answer{'read_rate_mb_sec'} = $1 + 0.0;
	    } elsif ($_ =~ m;^[[:space:]]*written, MiB/s:[[:space:]]*([[:digit:].]+);) {
		$op_answer{'write_rate_mb_sec'} = $1 + 0.0;
	    } elsif ($_ =~ m;^[[:space:]]*total time:[[:space:]]*([[:digit:].]+)s;) {
		$op_answer{'elapsed_time'} = $1 + 0.0;
	    } elsif ($_ =~ m;^[[:space:]]*min:[[:space:]]*([[:digit:].]+);) {
		$op_answer{'min_latency_sec'} = $1 / 1000.0;
	    } elsif ($_ =~ m;^[[:space:]]*avg:[[:space:]]*([[:digit:].]+);) {
		$op_answer{'avg_latency_sec'} = $1 / 1000.0;
	    } elsif ($_ =~ m;^[[:space:]]*max:[[:space:]]*([[:digit:].]+);) {
		$op_answer{'max_latency_sec'} = $1 / 1000.0;
	    } elsif ($_ =~ m;^[[:space:]]*95th percentile:[[:space:]]*([[:digit:].]+);) {
		$op_answer{'p95_latency_sec'} = $1 / 1000.0;
	    }
	    if ($ENV{"VERBOSE"} > 0) {
		chomp;
		timestamp($_);
	    }
	}
	close RUN;
	wait();
	my ($op1_user, $op1_sys) = cputime();
	$op_answer{'user_cpu_time'} = $op1_user - $op0_user;
	$op_answer{'sys_cpu_time'} = $op1_sys - $op0_sys;
	do_sync(idname("$mode+finish"));
	timestamp("Cleanup...");
	timestamp("sysbench --time=$runtime $sysbench_generic_args $sysbench_cmd cleanup --file-test-mode=$mode $sysbench_fileio_args");
	open(CLEANUP, "-|", "sysbench --time=$runtime $sysbench_generic_args $sysbench_cmd cleanup --file-test-mode=$mode $sysbench_fileio_args") || die "Can't run sysbench: $!\n";
	while (<CLEANUP>) {
	    if ($ENV{"VERBOSE"} > 0) {
		chomp;
		timestamp($_);
	    }
	}
	close CLEANUP;
	$op_answers{$mode} = \%op_answer;
    }
    my $data_end_time = xtime();
    my ($elapsed_time) = $data_end_time - $data_start_time;
    my ($base1_user, $base1_sys) = cputime();
    my ($user) = $base1_user - $base0_user;
    my ($sys) = $base1_sys - $base0_sys;
    my (%extras) = (
	'workloads' => \%op_answers
	);
    my ($answer) = print_json_report($data_start_time, $data_end_time, $elapsed_time, $user, $sys, \%extras);
    print STDERR "$answer\n";
    do_sync($answer);
}

run_workload($processes, \&runit);
