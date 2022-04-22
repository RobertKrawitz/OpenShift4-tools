#!/usr/bin/perl

use Time::HiRes qw(gettimeofday usleep);
use Time::Piece;
use File::Temp qw(tempfile);
use Socket;
use Sys::Hostname;
use strict;
use JSON;
use POSIX;

my %timing_parameters = ();
my ($last_sync_time) = -10;

sub cputime() {
    my (@times) = times();
    my ($usercpu) = $times[0] + $times[2];
    my ($syscpu) = $times[1] + $times[3];
    return ($usercpu, $syscpu);
}

sub xtime(;$) {
    my ($nocorrect) = @_;
    my (@now) = gettimeofday();
    my ($t) = $now[0] + ($now[1] / 1000000.0);
    if ((!defined $nocorrect || !$nocorrect) && defined $timing_parameters{'xtime_adjustment'}) {
	return $t - $timing_parameters{'xtime_adjustment'};
    } else {
	return $t;
    }
}

sub ts() {
    my (@now) = POSIX::modf(xtime(1) - $timing_parameters{'local_offset_from_sync'});
    return sprintf("%s.%06d", gmtime($now[1])->strftime("%Y-%m-%dT%T"), $now[0] * 1000000);
}
sub timestamp($) {
    my ($str) = @_;
    printf STDERR "%7d %s %s\n", $$, ts(), $str;
}

sub calibrate_time() {
    my ($time_overhead) = 0;
    for (my $i = 0; $i < 1000; $i++) {
        my ($start) = xtime();
	my ($end) = xtime();
	$time_overhead += $end - $start;
    }
    return $time_overhead / 1000;
}

sub drop_cache($$) {
    my ($service, $port) = @_;
    timestamp("Dropping local cache");
    system('sync');
    timestamp("Dropping host cache");
    my ($sock) = connect_to($service, $port);
    timestamp("Connected to $service:$port");
    my ($sbuf);
    my ($answer) = sysread($sock, $sbuf, 1024);
    timestamp("Got confirmation");
    close($sock);
}

sub initialize_timing($$$$$;$) {
    my ($basetime, $crtime, $sync_host, $sync_port, $name, $start_time) = @_;
    if (! defined $start_time) {
	($start_time) = xtime();
    }
    my ($presync) = "timestamp: %s $name";
    timestamp("About to sync");
    my ($local_sync_start, $remote_sync_start, $absolute_sync_start,
	$remote_sync_base, $remote_sync, $sync_base_start_time) = split(/ +/, do_sync($sync_host, $sync_port, $presync));
    timestamp("Done sync");
    my ($local_sync) = xtime();
    my ($local_sync_rtt) = $local_sync - $local_sync_start;
    my ($remote_sync_rtt) = $remote_sync - $remote_sync_start;
    my ($local_offset_from_sync) =
	($local_sync - $remote_sync) - (($local_sync_rtt - $remote_sync_rtt) / 2);
    my ($adjusted_start_time) = $start_time - $local_offset_from_sync;
    my ($start_offset_from_base) = $adjusted_start_time - $basetime;
    my ($local_offset_from_base) = $local_offset_from_sync + $start_offset_from_base;

    my ($sync_rtt_delta) = $local_sync_rtt - $remote_sync_rtt;
    my ($xtime_adjustment) = $basetime + $local_offset_from_sync;

    %timing_parameters = (
	'sync_pod_start' => $absolute_sync_start + 0.0,
	'controller_basetime' => $basetime + 0.0,
	'controller_crtime' => $crtime + 0.0,
	'local_offset_from_sync' => $local_offset_from_sync + 0.0,
	'local_start_time' => $adjusted_start_time + 0.0,
	'local_sync' => $local_sync + 0.0,
	'local_sync_rtt' => $local_sync_rtt + 0.0,
	'local_sync_start' => $local_sync_start + 0.0,
	'local_sync_time' => $local_sync + 0.0,
	'remote_sync' => $remote_sync + 0.0,
	'remote_sync_base' => $remote_sync_base + 0.0,
	'remote_sync_offset' => $remote_sync - $remote_sync_base + 0.0,
	'remote_sync_rtt' => $remote_sync_rtt + 0.0,
	'remote_sync_start' => $remote_sync_start + 0.0,
	'start_time' => $start_offset_from_base + 0.0,
	'sync_rtt_delta' => $sync_rtt_delta + 0.0,
	'xtime_adjustment' => $xtime_adjustment + 0.0,
	'remote_sync_base_start_time' => $sync_base_start_time + 0.0,
	'local_base_start_time' => $start_time + 0.0,
	'local_offset_from_sync' => $local_offset_from_sync + 0.0,
	'local_offset_from_base' => $local_offset_from_base + 0.0,
	);
    timestamp("Timing parameters:");
    map { timestamp(sprintf("%-32s %.6f", $_, $timing_parameters{$_})) } (sort keys %timing_parameters);
}

sub print_timing_parameters() {
    my ($answer) = join(",\n", map { "    \"$_\": $timing_parameters{$_}" } (sort keys %timing_parameters));
    return "{\n    $answer\n}";
}

sub get_timing_parameter($) {
    my ($parameter) = @_;
    return $timing_parameters{$parameter};
}

sub connect_to($$) {
    my ($addr, $port) = @_;
    my ($connected) = 0;
    my ($fname,$faliases,$ftype,$flen,$faddr);
    my ($sock);
    do {
        ($fname,$faliases,$ftype,$flen,$faddr) = gethostbyname($addr);
        my $sockaddr = "S n a4 x8";
        if (length($faddr) < 4) {
            print STDERR "Malformed address, waiting for addr for $addr\n";
            sleep(1);
        } else {
            my $straddr = inet_ntoa($faddr);
            my $sockmeta = pack($sockaddr, AF_INET, $port, $faddr);
            socket($sock, AF_INET, SOCK_STREAM, getprotobyname('tcp')) || die "can't make socket: $!";
            if (connect($sock, $sockmeta)) {
                $connected = 1;
            } else {
                timestamp("Could not connect to $addr on port $port: $!");
                close $sock;
                sleep(1);
            }
        }
    } while (! $connected);
    return ($sock);
}

sub print_json_report($$$$$$$;$) {
    my ($namespace, $pod, $container, $process_id, $data_start_time, $data_end_time,
	$data_elapsed_time, $user_cpu, $sys_cpu, $extra) = @_;
    my (%hash) = (
	'application' => 'clusterbuster-json',
	'namespace' => $namespace,
	'pod' => $pod,
	'container' => $container,
	'process_id' => $process_id,
	'pod_create_time' => get_timing_parameter('controller_crtime') - get_timing_parameter('controller_basetime'),
	'pod_start_time' => get_timing_parameter('start_time'),
	'data_start_time' => $data_start_time,
	'data_end_time' => $data_end_time,
	'data_elapsed_time' => $data_elapsed_time,
	'user_cpu_time' => $user_cpu,
	'system_cpu_time' => $sys_cpu,
	'cpu_time' => $user_cpu + $sys_cpu,
	'timing_parameters' => \%timing_parameters
	);
    
    map { $hash{$_} = $$extra{$_} } keys %$extra;
    return to_json(\%hash);
}

sub do_sync_internal($$$) {
    my ($addr, $port, $token) = @_;
    while (1) {
	timestamp("sync on $addr:$port");
	my ($sync_conn) = connect_to($addr, $port);
	my ($sbuf);
	my ($ntoken) = $token;
	if ($ntoken =~ /%s/) {
	    my ($time) = xtime();
	    $ntoken =~ s/%s/$time/;
	}
	my ($token_length) = sprintf('0x%08x', length $ntoken);
	my ($tbuf) = "$token_length$ntoken";
	my ($bytes_to_write) = length $tbuf;
	my ($offset) = 0;
	my ($answer);
	while ($bytes_to_write > 0) {
	    $answer = syswrite($sync_conn, $tbuf, length $tbuf, $offset);
	    if (length $tbuf > 128) {
		timestamp(sprintf("Writing %d bytes to sync", length $ntoken));
	    } else {
		timestamp("Writing token $tbuf to sync");
	    }
	    if ($answer <= 0) {
		timestamp("Write token failed: $!");
		exit(1);
	    } else {
		$bytes_to_write -= $answer;
		$offset += $answer;
	    }
	}
	$answer = sysread($sync_conn, $sbuf, 1024);
	if ($!) {
	    timestamp('sync failed, retrying');
	} else {
	    timestamp(sprintf('sync complete, response %s', $sbuf));
	    return $sbuf;
	}
    }
}

sub do_sync($$;$) {
    my ($addr, $port, $token) = @_;
    if (not $addr) { return; }
    my ($fh) = undef;
    my ($file) = undef;
    if ($addr eq '-') {
	$addr=`ip route get 1 |awk '{print \$(NF-2); exit}'`;
	chomp $addr;
    }
    if ($token && $token =~ /clusterbuster-json/) {
	$token =~ s,\n *,,g;
    } elsif (not $token) {
        $token = sprintf('%s %s-%d', ts(), hostname(), rand() * 999999999);
    } elsif (substr($token, 0, 10) ne 'timestamp:') {
	$token = ts() . " $token";
    }
    my ($answer) = do_sync_internal($addr, $port, $token);
    return $answer;
}

sub run_cmd_to_stderr(@) {
    my (@cmd) = @_;
    timestamp("@cmd output");
    if (open(my $fh, "-|", @cmd)) {
	while (<$fh>) {
	    print STDERR "$cmd[0] $_";
	}
	close($fh)
    } else {
	timestamp("Can't run $cmd[0]");
    }
}

sub finish($) {
    my ($exit_at_end) = @_;
    run_cmd_to_stderr("lscpu");
    run_cmd_to_stderr("dmesg");
    if ($exit_at_end) {
	timestamp("About to exit");
	while (wait() > 0) {}
	timestamp("Done waiting");
	print STDERR "FINIS\n";
	POSIX::_exit(0);
    } else {
	timestamp("Waiting forever");
	pause();
    }
}

1;
