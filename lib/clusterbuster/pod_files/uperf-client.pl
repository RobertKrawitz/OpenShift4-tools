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
    $exit_at_end, $synchost, $syncport, $loghost, $logport, $runtime,
    $srvhost, $connect_port, $iterations, @tests) = @ARGV;
my ($start_time, $data_start_time, $data_end_time, $elapsed_time, $end_time, $user, $sys, $cuser, $csys);
$start_time = xtime();

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
	my ($modifier) = $2;
	if ($modifier eq 'us') {
	    return $base * 1000000.0;
	} elsif ($modifier eq 'ns') {
	    return $base * 1000000000.0;
	} elsif ($modifier eq 's') {
	    return $base;
	} else {
	    return $base / 1000.0;
	}
    }
    return undef;
}

my (%results);
my (@cases);
my (@failed_cases) = ();

my ($ucpu0, $scpu0) = cputime();
foreach my $test (@tests) {
    my ($test_type, $proto, $size, $nthr) = split(/, */, $test);
    my ($base_test_name) = "${proto}-${test_type}-${size}B-${nthr}i";
    my (%options) = (
	'srvhost' => $srvhost,
	'proto' => $proto,
	'test_type' => $test_type,
	'size' => $size,
	'runtime' => $runtime,
	'nthr' => $nthr,
	);
    my ($test_template) = "$dir/uperf-${test_type}.xml";
    my ($testfile) = "/tmp/fio-test.xml";
    process_file($test_template, $testfile, %options);
    my (@iterations);
    my ($test_name) = sprintf('%04i-%s', $counter, $base_test_name);
    my (%metadata) = (
	'protocol' => $proto,
	'test_type' => $test_type,
	'message_size' => $size,
	'thread_count' => $nthr,
	'test_name' => $test_name
	);
    foreach my $iteration (1..$iterations) {
	my ($test_full_name) = sprintf('%04i-%02i-%s', $counter, $iteration, $base_test_name);
	my ($failed) = 0;
	do_sync($synchost, $syncport, "$namespace:$pod:$container:$$:$test_full_name");
	my ($job_start_time) = xtime();
	if (! defined $data_start_time) {
	    $data_start_time = $job_start_time;
	}
	timestamp("Running test $test_full_name");
	open(RUN, "-|", "uperf", "-f", "-P", "$connect_port", '-m', '/tmp/fio-test.xml', '-R', '-a', '-i', '.1', '-Tf') || die "Can't run uperf: $!\n";
	my (%data);
	my ($start_time) = 0;
	my ($last_time) = 0;
	my ($last_nbytes) = 0;
	my ($last_nops) = 0;
	my ($ts_count) = 0;
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
	    } elsif (/^[*]/) {
		timestamp($_);
	    } elsif (/WARNING: Errors/ && ! $failed) {
		$failed = 1;
		timestamp("Test case $test_full_name failed!");
		push @failed_cases, $test_full_name;
	    }
	}
	$data_end_time = xtime();
	$summary{'elapsed_time'} = $last_time - $start_time;
	$summary{'nbytes'} = $last_nbytes;
	$summary{'nops'} = $last_nops;
	$summary{'avg_ops_sec'} = $summary{'nops'} / $summary{'elapsed_time'};
	$summary{'avg_bytes_sec'} = $summary{'bytes'} / $summary{'elapsed_time'};
	$summary{'job_start'} = $job_start_time;
	$summary{'job_end'} = $data_end_time;
	$data{'timeseries'} = \@timeseries;
	$data{'summary'} = \%summary;
	$data{'metadata'} = \%metadata;
	$data{'status'} => (
	    'condition' => $failed ? 'FAIL' : 'PASS',
	    'message' => $failure_message,
	    );
	push @iterations, \%data;
	$elapsed_time += $summary{'elapsed_time'};
    }
    $counter++;
    my (%case) = (
	'metadata' => \%metadata,
	'iterations' => \@iterations,
	);
    push @cases, \%case;
}
$results{'test_cases'} = \@cases;
$results{'failed_cases'} = \@failed_cases;

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

finish($exit_at_end);
