#!/usr/bin/perl

use strict;
use JSON;
use POSIX;
use Getopt::Long;

Getopt::Long::Configure("bundling", "no_ignore_case", "pass_through");

my ($mode);
my (@rows);
while (<>) {
    chomp;
    $_ =~ s,\r,,;
    my (@row) = split(/[, ]/);
    if (! defined $mode) {
	if ($row[2] =~ /-soaker-/) {
	    $mode = 'cpu-soaker';
	} elsif ($row[2] =~ /-client-/) {
	    $mode = 'client-server';
	} elsif ($row[2] =~ /-sysbench-/) {
	    $mode = 'sysbench';
	} elsif ($row[2] =~ /-files-/) {
	    $mode = 'files';
	} else {
	    die "Unrecognized mode from $row[2]!\n";
	}
    }
    unshift @row, $_;
    push @rows, \@row;
}

my (%data);
$data{'mode'} = $mode;
my ($first_start) = 1 << 30;
my ($last_start) = -$first_start;
my ($first_end) = $first_start;
my ($last_end) = $last_start;
my ($total_cpu) = 0.0;
my ($total_cpu_util) = 0.0;
my ($total_iterations) = 0;
my ($total_et) = 0.0;

if ($mode eq 'cpu-soaker') {
    process_cpusoaker(\%data, @rows);
} elsif ($mode eq 'client-server') {
    process_clientserver(\%data, @rows);
} elsif ($mode eq 'sysbench') {
    process_sysbench(\%data, @rows);
} elsif ($mode eq 'files') {
    process_files(\%data, @rows);
}
my ($json) = JSON->new->ascii->pretty->indent->canonical;
$json = $json->encode({%data});
print $json;

sub roundto($;$) {
    my ($number, $digits) = @_;
    if (! defined $digits) {
	$digits = 0;
    }
    my ($scale) = 10 ** $digits;
    return (POSIX::lround($number * $scale) / $scale);
}

sub process_cpusoaker(\%@) {
    my ($data, @rows) = @_;
    foreach my $row (@rows) {
	my ($namespace) = $$row[2];
	my ($pod) = $$row[3];
	my ($container) = $$row[5];
	my ($pid) = $$row[11];
	my ($init_et) = 0.0 + $$row[12];
	my ($container_start) = 0.0 + $$row[13];
	my ($run_start) = 0.0 + $$row[14];
	my ($runtime) = 0.0 + $$row[15];
	my ($run_end) = 0.0 + $$row[16];
	my ($cpu) = 0.0 + $$row[17];
	my ($cpu_util) = $$row[18] / 100.0;
	my ($iterations) = 0 + $$row[19];
	my ($iterations_per_sec) = 0 + $$row[20];
	if ($run_start < $first_start) { $first_start = $run_start; }
	if ($run_end < $first_end) { $first_end = $run_end; }
	if ($run_end > $last_end) { $last_end = $run_end; }
	if ($run_start > $last_start) { $last_start = $run_start; }
	my (%rowhash) = ();
	$rowhash{'raw_result'} = $$row[0];
	$rowhash{'namespace'} = $namespace;
	$rowhash{'pod'} = $pod;
	$rowhash{'container'} = $container;
	$rowhash{'pid'} = $pid;
	$rowhash{'init_et'} = $init_et;
	$rowhash{'container_start_relative'} = $container_start;
	$rowhash{'run_start'} = $run_start;
	$rowhash{'runtime'} = $runtime;
	$rowhash{'run_end'} = $run_end;
	$rowhash{'cpu_time'} = $cpu;
	$rowhash{'cpu_utilization'} = $cpu_util;
	$rowhash{'iterations'} = $iterations;
	$rowhash{'iterations_per_sec'} = $iterations_per_sec;
	$total_cpu += $cpu;
	$total_cpu_util += $cpu_util; # Iffy
	$total_iterations += $iterations;
	$total_et += $runtime;

	push @{$$data{'rows'}}, \%rowhash;
    }
    $$data{'summary'}{'first_run_start'} = $first_start;
    $$data{'summary'}{'first_run_end'} = $first_end;
    $$data{'summary'}{'last_run_start'} = $last_start;
    $$data{'summary'}{'last_run_end'} = $last_end;
    $$data{'summary'}{'total_iterations'} = $total_iterations;
    $$data{'summary'}{'iterations_per_cpu_sec'} = roundto($total_cpu <= 0 ? 0 : $total_iterations / $total_cpu);
    $$data{'summary'}{'iterations_per_sec'} = roundto($total_et <= 0 ? 0 : $total_iterations * ($#rows + 1) / $total_et);
    $$data{'summary'}{'elapsed_time_average'} = roundto($total_et / ($#rows + 1), 3);
    $$data{'summary'}{'elapsed_time_net'} = roundto($last_end - $first_start, 3);
    $$data{'summary'}{'overlap_error'} = roundto(((($last_start - $first_start)+($last_end - $first_end)) / 2) / ($total_et / ($#rows + 1)), 5);
    $$data{'summary'}{'total_cpu_utiization'} = roundto($total_cpu_util, 3);
}

sub process_clientserver(\%$) {
    my ($data, @rows) = @_;
    my ($total_max_round_trip_time) = 0;
    my ($round_trip_time_accumulator) = 0;
    my ($total_data_rate) = 0;
    my ($total_data_xfer) = 0;
    foreach my $row (@rows) {
	my ($namespace) = $$row[2];
	my ($pod) = $$row[3];
	my ($container) = $$row[5];
	my ($run_start) = 0.0 + $$row[15];
	my ($run_end) = 0.0 + $$row[16];
	my ($runtime) = 0.0 + $$row[21];
	my ($mean_round_trip_time) = 0.0 + $$row[23];
	my ($max_round_trip_time) = 0.0 + $$row[24];
	my ($iterations) = $$row[27];
	my ($data_xfer) = $$row[20];
	if ($run_start < $first_start) { $first_start = $run_start; }
	if ($run_end < $first_end) { $first_end = $run_end; }
	if ($run_end > $last_end) { $last_end = $run_end; }
	if ($run_start > $last_start) { $last_start = $run_start; }
	if ($max_round_trip_time > $total_max_round_trip_time) {
	    $total_max_round_trip_time = $max_round_trip_time;
	}
	my (%rowhash) = ();
	$rowhash{'raw_result'} = $$row[0];
	$rowhash{'namespace'} = $namespace;
	$rowhash{'pod'} = $pod;
	$rowhash{'container'} = $container;
	$rowhash{'run_start'} = $run_start;
	$rowhash{'runtime'} = $runtime;
	$rowhash{'run_end'} = $run_end;
	$rowhash{'mean_round_trip_time'} = $mean_round_trip_time;
	$rowhash{'max_round_trip_time'} = $max_round_trip_time;
	$rowhash{'iterations'} = $iterations;
	$rowhash{'data_xfer'} = $data_xfer;
	$rowhash{'data_rate'} = roundto($data_xfer / $runtime, 3);

	$total_data_xfer += $data_xfer;
	$total_iterations += $iterations;
	$total_et += $runtime;
	$round_trip_time_accumulator += $mean_round_trip_time;
	push @{$$data{'rows'}}, \%rowhash;
    }
    $$data{'summary'}{'first_run_start'} = $first_start;
    $$data{'summary'}{'first_run_end'} = $first_end;
    $$data{'summary'}{'last_run_start'} = $last_start;
    $$data{'summary'}{'last_run_end'} = $last_end;
    $$data{'summary'}{'elapsed_time_average'} = roundto($total_et / ($#rows + 1), 3);
    $$data{'summary'}{'elapsed_time_net'} = roundto($last_end - $first_start, 3);
    $$data{'summary'}{'overlap_error'} = roundto(1.0 - (($total_et / ($#rows + 1)) / ($last_end - $first_start)), 4);
    $$data{'summary'}{'total_iterations'} = $total_iterations;
    $$data{'summary'}{'max_round_trip_time'} = $total_max_round_trip_time;
    $$data{'summary'}{'total_data_xfer'} = $total_data_xfer;
    $$data{'summary'}{'average_round_trip_time'} = $round_trip_time_accumulator / ($#rows + 1);
}

sub process_sysbench(\%$) {
    my ($data, @rows) = @_;
    foreach my $row (@rows) {
	my ($namespace) = $$row[2];
	my ($pod) = $$row[3];
	my ($container) = $$row[5];
	my ($run_start) = 0.0 + $$row[12];
	my ($run_end) = 0.0 + $$row[14];
	my ($runtime) = 0.0 + $$row[20];
	my (%rowhash) = ();
	if ($run_start < $first_start) { $first_start = $run_start; }
	if ($run_end < $first_end) { $first_end = $run_end; }
	if ($run_end > $last_end) { $last_end = $run_end; }
	if ($run_start > $last_start) { $last_start = $run_start; }
	$rowhash{'raw_result'} = $$row[0];
	$rowhash{'namespace'} = $namespace;
	$rowhash{'pod'} = $pod;
	$rowhash{'container'} = $container;
	$rowhash{'run_start'} = $run_start;
	$rowhash{'runtime'} = $runtime;
	$rowhash{'run_end'} = $run_end;
    }
    $$data{'summary'}{'first_run_start'} = $first_start;
    $$data{'summary'}{'first_run_end'} = $first_end;
    $$data{'summary'}{'last_run_start'} = $last_start;
    $$data{'summary'}{'last_run_end'} = $last_end;
}

sub process_files(\%$) {
    my ($data, @rows) = @_;
    foreach my $row (@rows) {
	my ($namespace) = $$row[2];
	my ($pod) = $$row[3];
	my ($container) = $$row[5];
	my ($run_start) = 0.0 + $$row[15];
	my ($run_end) = 0.0 + $$row[16];
	my ($runtime) = 0.0 + $$row[21];
	my (%rowhash) = ();
	if ($run_start < $first_start) { $first_start = $run_start; }
	if ($run_end < $first_end) { $first_end = $run_end; }
	if ($run_end > $last_end) { $last_end = $run_end; }
	if ($run_start > $last_start) { $last_start = $run_start; }
	$rowhash{'raw_result'} = $$row[0];
	$rowhash{'namespace'} = $namespace;
	$rowhash{'pod'} = $pod;
	$rowhash{'container'} = $container;
	$rowhash{'run_start'} = $run_start;
	$rowhash{'runtime'} = $runtime;
	$rowhash{'run_end'} = $run_end;
    }
    $$data{'summary'}{'first_run_start'} = $first_start;
    $$data{'summary'}{'first_run_end'} = $first_end;
    $$data{'summary'}{'last_run_start'} = $last_start;
    $$data{'summary'}{'last_run_end'} = $last_end;
}
