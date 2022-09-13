#!/usr/bin/perl

use Time::HiRes qw(gettimeofday usleep);
use Time::Piece;
use Socket;
use Sys::Hostname;
use JSON;
use POSIX;
use Scalar::Util qw(looks_like_number);
use strict;

my %timing_parameters = ();

my ($namespace, $container, $basetime, $baseoffset, $crtime, $exit_at_end, $synchost, $syncport, $start_time, $pod);

sub _xtime() {
    my (@now) = gettimeofday();
    return $now[0] + ($now[1] / 1000000.0);
}

sub _run_cmd(@) {
    my (@cmd) = @_;
    if (open(my $fh, "-|", @cmd)) {
	return get_timestamp(sprintf("%s output:\n%s", join(" ", @cmd), do { local $/; <$fh>; }));
    } else {
	timestamp("Can't run $cmd[0]");
    }
}

sub _clean_numbers($) {
    # Perl to_json encodes innfinity as inf and NaN as nan.
    # This results in invalid JSON.  It's our responsibility to sanitize
    # this up front.
    # Discussion: https://perlmaven.com/parsing-nan-in-json
    # Python has similar issues:
    # https://docs.python.org/3.8/library/json.html#infinite-and-nan-number-values
    my ($ref) = @_;
    if (ref $ref eq 'HASH') {
	my (%answer);
	map { $answer{$_} = _clean_numbers($$ref{$_})} keys %$ref;
	return \%answer;
    } elsif (ref $ref eq 'ARRAY') {
	my (@answer) = map {_clean_numbers($_)} @$ref;;
	return \@answer;
    } elsif (ref $ref eq '' && looks_like_number($ref) && $ref != 0 &&
	     (! defined ($ref <=> 0) || ((1 / $ref) == 0))) {
	return undef;
    } else {
	return $ref
    }
}

sub _ts() {
    my (@now) = POSIX::modf(_xtime() - $timing_parameters{'local_offset_from_sync'});
    return sprintf("%s.%06d", gmtime($now[1])->strftime("%Y-%m-%dT%T"), $now[0] * 1000000);
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

sub cputime() {
    my (@times) = times();
    my ($usercpu) = $times[0] + $times[2];
    my ($syscpu) = $times[1] + $times[3];
    return ($usercpu, $syscpu);
}

sub xtime() {
    my ($t) = _xtime();
    if (defined $timing_parameters{'xtime_adjustment'}) {
	return $t - $timing_parameters{'xtime_adjustment'};
    } else {
	return $t;
    }
}

sub get_timestamp($) {
    my ($str) = @_;
    $str =~ s/\n(.*\S.*)/\n            $1/g;
    sprintf("%7d %s %s\n", $$, _ts(), $str);
}

sub timestamp($) {
    my ($str) = @_;
    print STDERR get_timestamp($str);
}

sub drop_cache($$) {
    my ($service, $port) = @_;
    timestamp("Dropping local cache");
    system('sync');
    timestamp("Dropping host cache:");
    my ($sock) = connect_to($service, $port);
    timestamp("    Connected to $service:$port");
    my ($sbuf);
    my ($answer) = sysread($sock, $sbuf, 1024);
    timestamp("    Confirmed");
    close($sock);
}

sub podname() {
    return $pod;
}

sub container() {
    return $container;
}

sub namespace() {
    return $namespace;
}

sub idname(;@) {
    my (@extra_components) = @_;
    my ($sep) = ':';
    if ($extra_components[0] eq '-d') {
	$sep = '-';
	shift @extra_components;
    }
    return join($sep, $namespace, $pod, $container, $$, @extra_components);
}

sub parse_command_line(@) {
    my (@argv) = @_;
    my (@rest);
    ($namespace, $container, $basetime, $baseoffset, $crtime, $exit_at_end, $synchost, $syncport, @rest) = @argv;
    $start_time = xtime();
    $pod = hostname;
    return @rest;
}

sub initialize_timing(;@) {
    my (@name_components) = @_;
    if (! defined $start_time) {
	($start_time) = xtime();
    }
    my ($name) = join(':', $namespace, $pod, $container, $$, @name_components);
    my ($presync) = "timestamp: %s $name";
    timestamp("About to sync");
    my ($local_sync_start, $remote_sync_start, $absolute_sync_start,
	$remote_sync_base, $remote_sync, $sync_base_start_time) = split(/ +/, _do_sync_command('TIME', $presync));
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
    $basetime += $baseoffset;
    $crtime += $baseoffset;
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

sub _do_sync_command($$) {
    my ($command, $token) = @_;
    if (lc $command eq 'sync' && not $token) {
        $token = sprintf('%s %s-%d', _ts(), hostname(), rand() * 999999999);
    }
    $token = "$command $token";
    while (1) {
	timestamp("sync on $synchost:$syncport");
	my ($sync_conn) = connect_to($synchost, $syncport);
	if ($token =~ /%s/) {
	    my ($time) = xtime();
	    $token =~ s/%s/$time/;
	}
	my ($token_length) = sprintf('0x%08x', length $token);
	my ($tbuf) = "$token_length$token";
	my ($bytes_to_write) = length $tbuf;
	my ($offset) = 0;
	my ($answer);
	while ($bytes_to_write > 0) {
	    $answer = syswrite($sync_conn, $tbuf, length $tbuf, $offset);
	    if (length $tbuf > 128) {
		timestamp(sprintf("Writing %s bytes to sync", $token_length));
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
	my ($sbuf);
	$answer = sysread($sync_conn, $sbuf, 1024);
	if ($!) {
	    timestamp('sync failed, retrying');
	} else {
	    timestamp(sprintf('sync complete, response %s', $sbuf));
	    return $sbuf;
	}
    }
}

sub finish(;$$) {
    my ($status, $pid) = @_;
    my ($answer) = _run_cmd("lscpu");
    $answer .= _run_cmd("dmesg");
    print STDERR $answer;
    
    if (defined $status && $status != 0) {
	print STDERR "FAIL!\n";
	my ($buf) = sprintf("Namespace/pod/container: %s/%s/%s%s\n%s\n", $namespace, $pod, $container, (defined $pid ? " pid: $pid" : ""), $answer);
	$buf .= sprintf("Run:\noc logs -n '%s' '%s' -c '%s'\n", $namespace, $pod, $container);
	_do_sync_command('FAIL', $buf);
	if ($exit_at_end) {
	    POSIX::_exit($status);
	}
    }
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

sub run_workload($;$@) {
    my ($run_func, $processes, @args) = @_;
    if ($processes < 1) {
	$processes = 1;
    }
    my (%pids) = ();
    for (my $i = 0; $i < $processes; $i++) {
	my $child;
	if (($child = fork()) == 0) {
	    &$run_func($i, @args);
	    exit(0);
	} else {
	    $pids{$child} = 1;
	}
    }
    while (%pids) {
	my ($child) = wait();
	if ($child == -1) {
	    finish();
	} elsif (defined $pids{$child}) {
	    if ($?) {
		timestamp("Pid $child returned status $?!");
		finish($?, $child);
	    }
	    delete $pids{$child};
	}
    }
    finish();
}

sub report_results($$$$$;$) {
    my ($data_start_time, $data_end_time, $data_elapsed_time, $user_cpu, $sys_cpu, $extra) = @_;
    my (%hash) = (
	'application' => 'clusterbuster-json',
	'namespace' => $namespace,
	'pod' => $pod,
	'container' => $container,
	'process_id' => $$,
	'pod_create_time' => $timing_parameters{'controller_crtime'} - $timing_parameters{'controller_basetime'},
	'pod_start_time' => $timing_parameters{'start_time'},
	'data_start_time' => $data_start_time,
	'data_end_time' => $data_end_time,
	'data_elapsed_time' => $data_elapsed_time,
	'user_cpu_time' => $user_cpu,
	'system_cpu_time' => $sys_cpu,
	'cpu_time' => $user_cpu + $sys_cpu,
	'timing_parameters' => \%timing_parameters
	);
    
    map { $hash{$_} = $$extra{$_} } keys %$extra;
    my ($json) = to_json(_clean_numbers(\%hash));
    _do_sync_command('RSLT', $json);
    return $json;
}

sub sync_to_controller(;$) {
    my ($token) = @_;
    _do_sync_command('SYNC', $token);
}

1;
