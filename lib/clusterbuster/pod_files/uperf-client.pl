#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::HiRes qw(gettimeofday usleep);
use Time::Piece;
use Sys::Hostname;
use File::Basename;
my ($dir) = $ENV{'BAK_CONFIGMAP'};
require "$dir/clientlib.pl";

my ($namespace, $container, $basetime, $baseoffset, $crtime,
    $exit_at_end, $synchost, $syncport, $loghost, $logport, $runtime, $ramp_time,
    $srvhost, $connect_port, @tests) = @ARGV;
my ($start_time, $data_start_time, $data_end_time, $elapsed_time, $end_time, $user, $sys, $cuser, $csys);
$start_time = xtime();
my ($processes) = 1;		# Not using multi-process here

$SIG{TERM} = sub { POSIX::_exit(0); };
$basetime += $baseoffset;
$crtime += $baseoffset;

my ($data_sent);
my ($mean_latency, $max_latency, $stdev_latency);

my $pass = 0;
my $ex = 0;
my $ex2 = 0;
my ($cfail) = 0;
my ($refused) = 0;
my ($pod) = hostname;
initialize_timing($basetime, $crtime, $synchost, $syncport, "$namespace:$pod:$container", $start_time);
$start_time = get_timing_parameter('start_time');

$SIG{TERM} = sub { POSIX::_exit(0); };
timestamp("Clusterbuster uperf client starting");

sub process_file($$%) {
    my ($infile, $outfile, %options) = @_;
    my ($contents);
    open IN, "<", "$infile" || die "Can't read $infile: $!\n";
    while (<IN>) {
	$contents .= $_;
    }
    close IN;
    foreach my $key (keys %options) {
	$contents =~ s/%{$key}/$options{$key}/g;
    }
    open OUT, ">", "$outfile" || die "Can't create $outfile: $!\n";
    print OUT $contents;
    close OUT || die "Can't close $outfile: $!\n";
}

my (%options) = (
    'srvhost' => $srvhost,
    'runtime' => 1,
);

process_file("$dir/uperf-mini.xml", "/tmp/fio-test.xml", %options);
# Ensure that uperf server is running before we try to do anything.
timestamp("Waiting for uperf server $srvhost:$connect_port to come online...");
system("bash", "-c", "until uperf -P $connect_port -m /tmp/fio-test.xml >/dev/null; do sleep 1; done");
timestamp("Connected to uperf server");

my ($counter) = 1;

sub compute_seconds($) {
    my ($value) = @_;
    if ($value =~ /^([[:digit:]]+(\.[[:digit:]]*)?)(ns|us|ms|s)$/) {
	my ($base) = $1;
	my ($modifier) = $3;
	if ($modifier eq 'us') {
	    return $base / 1000000.0;
	} elsif ($modifier eq 'ns') {
	    return $base / 1000000000.0;
	} elsif ($modifier eq 's') {
	    return $base / 1.0;
	} else {
	    return $base / 1000.0;
	}
    }
    return undef;
}

my (%results);
my (%cases);
my (@failed_cases) = ();

sub runit() {
    my ($ucpu0, $scpu0) = cputime();
    foreach my $test (@tests) {
	my ($test_type, $proto, $size, $nthr) = split(/, */, $test);
	my ($base_test_name) = "${proto}-${test_type}-${size}B-${nthr}i";
	my (%options) = (
	    'srvhost' => $srvhost,
	    'proto' => $proto,
	    'test_type' => $test_type,
	    'size' => $size,
	    'runtime' => $runtime + (2 * $ramp_time),
	    'nthr' => $nthr,
	    );
	my ($test_template) = "$dir/uperf-${test_type}.xml";
	my ($testfile) = "/tmp/fio-test.xml";
	process_file($test_template, $testfile, %options);
	my ($test_name) = sprintf('%04i-%s', $counter, $base_test_name);
	my (%metadata) = (
	    'protocol' => $proto,
	    'test_type' => $test_type,
	    'message_size' => $size,
	    'thread_count' => $nthr,
	    'test_name' => $test_name
	    );
	my ($failed) = 0;
	do_sync($synchost, $syncport, "$namespace:$pod:$container:$$:$test_name");
	timestamp("Running test $test_name");
	system("cat /tmp/fio-test.xml 1>&2");
	my ($job_start_time) = xtime();
	if (! defined $data_start_time) {
	    $data_start_time = $job_start_time;
	}
	open(RUN, "-|", "uperf", "-f", "-P", "$connect_port", '-m', '/tmp/fio-test.xml', '-R', '-a', '-i', '1', '-Tf') || die "Can't run uperf: $!\n";
	my ($start_time) = 0;
	my ($last_time) = 0;
	my ($last_nbytes) = 0;
	my ($last_nops) = 0;
	my ($ts_count) = 0;
	my (%case);
	my (@timeseries);
	my (%threads);
	my (%flowops);
	my (%summary) = (
	    'write' => {},
	    'read' => {},
	    'total' => {},
	    );
	my ($failure_message) = '';
	while (<RUN>) {
	    chomp;
	    timestamp($_);
	    if (/^timestamp_ms:([[:digit:].]+) +name:([[:alnum:]]+) +nr_bytes:([[:digit:]]+) +nr_ops:([[:digit:]]+)/) {
		my ($ts) = $1 / 1000.0;
		my ($name) = $2;
		my ($nbytes) = $3 + 0.0;
		my ($nops) = $4 + 0.0;
		# We only care about Txn2 and threads; the other transactions are start
		# and finish, and we want to ignore those
		if ($name eq 'Txn2') {
		    if ($start_time == 0) {
			$start_time = $ts;
			$last_time = $ts;
		    } else {
			my (%row) = (
			    'time' => $ts - $start_time,
			    'timedelta' => $ts - $last_time,
			    'bytes' => $nbytes - $last_nbytes,
			    'nops' => $nops - $last_nops,
			    );
			push @timeseries, \%row;
			$last_time = $ts;
			$last_nbytes = $nbytes;
			$last_nops = $nops;
		    }
		} elsif ($name =~ /^Thr([[:digit:]])+/) {
		    my (%row) = (
			'time' => $ts - $start_time,
			'bytes' => $nbytes,
			'nops' => $nops,
			);
		    $threads{$name} = %row;
		}
	    } elsif (/^(Txn1|write|read)[ \t]/) {
		my ($op, $count, $avg, $cpu, $max, $min) = split;
		if ($op eq 'Txn1') {
		    $op = 'total';
		}
		$summary{$op}{'time_avg'} = compute_seconds($avg);
		$summary{$op}{'time_max'} = compute_seconds($max);
		$summary{$op}{'time_min'} = compute_seconds($min);
	    } elsif (/^[*][*] Error/) {
		$failure_message = $_;
		$failed = 1;
		timestamp("Test case $test_name failed!");
		push @failed_cases, $test_name;
	    } elsif (/^[*]/) {
		timestamp($_);
	    } elsif (/WARNING: Errors/ && ! $failed) {
		$failure_message = $_;
		$failed = 1;
		timestamp("Test case $test_name failed!");
		push @failed_cases, $test_name;
	    }
	}
	close(RUN);
	$data_end_time = xtime();
	$summary{'raw_elapsed_time'} = $last_time - $start_time;
	$summary{'raw_nbytes'} = $last_nbytes;
	$summary{'raw_nops'} = $last_nops;
	if ($summary{'raw_elapsed_time'} > 0) {
	    $summary{'raw_avg_ops_sec'} = $summary{'raw_nops'} / $summary{'raw_elapsed_time'};
	    $summary{'raw_avg_bytes_sec'} = $summary{'raw_nbytes'} / $summary{'raw_elapsed_time'};
	}
	$summary{'nbytes'} = 0;
	$summary{'nops'} = 0;
	$summary{'elapsed_time'} = 0;
	$summary{'avg_bytes_sec'} = 0;
	$summary{'avg_ops_sec'} = 0;
	my ($ops_sec_sum) = 0;
	my ($ops_sec_sq_sum) = 0;
	my ($bytes_sec_sum) = 0;
	my ($bytes_sec_sq_sum) = 0;
	my ($stdev_counter) = 0;
	map {
	    $summary{'nbytes'} += $$_{'bytes'};
	    $summary{'nops'} += $$_{'nops'};
	    $summary{'elapsed_time'} += $$_{'timedelta'};
	    my ($ops_sec) = $$_{'nops'} / $$_{'timedelta'};
	    my ($bytes_sec) = $$_{'bytes'} / $$_{'timedelta'};
	    $ops_sec_sum += $ops_sec;
	    $ops_sec_sq_sum += $ops_sec * $ops_sec;
	    $bytes_sec_sum += $bytes_sec;
	    $bytes_sec_sq_sum += $bytes_sec * $bytes_sec;
	    $stdev_counter++;
	} grep { ($summary{'raw_elapsed_time'} < 10 ||
		  ($$_{'time'} >= $ramp_time &&
		   $$_{'time'} < $summary{'raw_elapsed_time'} - $ramp_time)) } @timeseries;
	if ($summary{'elapsed_time'} > 0) {
	    $summary{'avg_bytes_sec'} = $summary{'nbytes'} / $summary{'elapsed_time'};
	    $summary{'avg_ops_sec'} = $summary{'nops'} / $summary{'elapsed_time'};
	    $summary{'bytes_sec_sq_sum'} = $bytes_sec_sq_sum;
	    $summary{'bytes_sec_sum'} = $bytes_sec_sum;
	    $summary{'ops_sec_sq_sum'} = $ops_sec_sq_sum;
	    $summary{'ops_sec_sum'} = $ops_sec_sum;
	    if ($stdev_counter >= 2) {
		$summary{'stdev_bytes_sec'} = (($bytes_sec_sq_sum / $stdev_counter) - ($summary{'avg_bytes_sec'} ** 2)) ** 0.5;
		$summary{'stdev_ops_sec'} = (($ops_sec_sq_sum / $stdev_counter) - ($summary{'avg_ops_sec'} ** 2)) ** 0.5;
	    } else {
		$summary{'stdev_bytes_sec'} = 0;
		$summary{'stdev_ops_sec'} = 0;
	    }
	}
	$summary{'job_start'} = $job_start_time;
	$summary{'job_end'} = $data_end_time;
	$case{'status'}{'condition'} = $failed ? 'FAIL' : 'PASS';
	$case{'status'}{'message'} = $failure_message;
	$case{'metadata'} = \%metadata;
	$case{'summary'} = \%summary;
	$case{'timeseries'} = \@timeseries;
	$elapsed_time += $summary{'elapsed_time'};
	$counter++;
	$cases{$test_name} = \%case;
    }
    $results{'results'} = \%cases;
    $results{'failed'} = \@failed_cases;

    my ($ucpu1, $scpu1) = cputime();
    $ucpu1 -= $ucpu0;
    $scpu1 -= $scpu0;

    my ($results) = print_json_report($namespace, $pod, $container, $$, $data_start_time,
				      $data_end_time, $elapsed_time, $ucpu1, $scpu1, \%results);
    timestamp("Done");
    if ($syncport) {
	do_sync($synchost, $syncport, $results);
    }
    if ($logport > 0) {
	do_sync($loghost, $logport, $results);
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
