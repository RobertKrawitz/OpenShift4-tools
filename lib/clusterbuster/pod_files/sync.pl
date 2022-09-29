#!/usr/bin/perl
use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday usleep);
use JSON;
use Scalar::Util qw(looks_like_number);

my ($verbose, $sync_file, $error_file, $controller_timestamp_file);
my ($offset_from_controller) = 0;
my ($predelay) = 0;
my ($postdelay) = 0;
use Getopt::Long;
Getopt::Long::Configure("bundling", "no_ignore_case", "pass_through");
GetOptions("v!"  => \$verbose,
	   "t:s" => \$controller_timestamp_file,
	   "d:i" => \$predelay,
	   "D:i" => \$postdelay,
	   "f:s" => \$sync_file,
	   "e:s" => \$error_file);

my ($listen_port, $expected_clients, $initial_expected_clients, $sync_count) = @ARGV;
if ($sync_count < 1 || $expected_clients < 1) {
    timestamp("Sync requested with no clients or no syncs");
    POSIX::exit(0);
}

if ($initial_expected_clients <= 0) {
    $initial_expected_clients = $expected_clients;
}

sub xtime() {
    my (@now) = gettimeofday();
    return $now[0] + ($now[1] / 1000000.0);
}

sub clean_numbers($) {
    # Perl to_json encodes innfinity as inf and NaN as nan.
    # This results in invalid JSON.  It's our responsibility to sanitize
    # this up front.
    my ($ref) = @_;
    if (ref $ref eq 'HASH') {
	my (%answer);
	map { $answer{$_} = clean_numbers($$ref{$_})} keys %$ref;
	return \%answer;
    } elsif (ref $ref eq 'ARRAY') {
	my (@answer) = map {clean_numbers($_)} @$ref;
	return \@answer;
    } elsif (ref $ref eq '' && looks_like_number($ref) && $ref != 0 &&
	     (! defined ($ref <=> 0) || ((1 / $ref) == 0))) {
	return undef;
    } else {
	return $ref
    }
}

sub touch($) {
    my ($file) = @_;
    open FILE, ">", $file || die "Can't open $file: $!\n";
    close FILE || die "Can't close $file: $!\n";
}
sub ytime() {
    return xtime() + $offset_from_controller;
}

sub timestamp($) {
    my ($str) = @_;
    my (@now) = POSIX::modf(ytime());
    printf STDERR  "sync %s.%06d %s\n", gmtime(int($now[1]))->strftime("%Y-%m-%dT%T"), $now[0] * 1000000, $str;
}

sub read_token($) {
    my ($client) = @_;
    my ($tbuf) = '';
    if (sysread($client, $tbuf, 10) != 10) {
	timestamp("Unable to read token");
	return undef;
    }
    if (!($tbuf =~ /0x[[:xdigit:]]{8}/)) {
	timestamp("Bad token $tbuf!");
	return undef;
    }
    my ($bytes_to_read) = hex($tbuf);
    $tbuf = '';
    my ($offset) = 0;
    while ($bytes_to_read > 0) {
	my ($bytes) = sysread($client, $tbuf, $bytes_to_read, $offset);
	if ($bytes == 0) {
	    timestamp("Short read: got zero bytes with $bytes_to_read left at $offset");
	    return undef;
	} elsif ($bytes < 0) {
	    timestamp("Bad read with $bytes_to_read left at $offset: $!");
	    return undef;
	} else {
	    $bytes_to_read -= $bytes;
	    $offset += $bytes;
	}
    }
    return $tbuf
}

sub get_port($) {
    my ($listen_port) = @_;
    my $sockaddr = "S n a4 x8";
    my $sock;
    socket($sock, AF_INET, SOCK_STREAM, getprotobyname('tcp')) || die "socket: $!";
    $SIG{TERM} = sub { close SOCK; POSIX::_exit(0); };
    setsockopt($sock,SOL_SOCKET, SO_REUSEADDR, pack("l",1)) || die "setsockopt reuseaddr: $!\n";
    setsockopt($sock,SOL_SOCKET, SO_KEEPALIVE, pack("l",1)) || die "setsockopt keepalive: $!\n";
    bind($sock, pack($sockaddr, AF_INET, $listen_port, "\0\0\0\0")) || die "bind: $!\n";
    my $mysockaddr = getsockname($sock);
    my ($junk, $port, $addr) = unpack($sockaddr, $mysockaddr);
    die "can't get port $port: $!\n" if ($port ne $listen_port);
    return $sock;
}

sub get_controller_timing($) {
    # Normalize time to the run host.  We collect two timestamps on the run host
    # bracketing one taken here, giving us an approximate delta between the two
    # hosts.  We assume that the second timestamp on the host is taken closer to
    # the sync host timestamp on the grounds that setting up the oc exec
    # is slower than tearing it down, but in either event, we know what the worst
    # case error is.
    timestamp("Waiting to receive controller time data");
    my ($timestamp_file) = @_;
    if ($timestamp_file) {
	while (! -f $timestamp_file) {
	    usleep(100000);
	}
	open TIMESTAMP, "<", $timestamp_file || die "Can't open timestamp file $timestamp_file: $!\n";
	my ($controller_json_data) = "";
	while (<TIMESTAMP>) {
	    $controller_json_data .= $_;
	}
	close TIMESTAMP;
	timestamp("Timestamp data: $controller_json_data");
	my ($controller_timestamp_data) = from_json($controller_json_data);
	$$controller_timestamp_data{'offset_from_controller'} = $$controller_timestamp_data{'second_controller_ts'} - $$controller_timestamp_data{'sync_ts'};
	unlink($timestamp_file);
	return $controller_timestamp_data;
    }
}

sub handle_rslt($$$) {
    my ($tmp_sync_file_base, $expected_clients, $tbuf) = @_;
    if (defined $tmp_sync_file_base) {
	my ($tmp_sync_file) = sprintf("%s-%d", $tmp_sync_file_base, $expected_clients);
	chomp $tbuf;
	open TMP, ">", "$tmp_sync_file" || die("Can't open sync file $tmp_sync_file: $!\n");
	print TMP "$tbuf\n";
	close TMP || die "Can't close sync file: $!\n";
    }
}

sub reply_timestamp($$\@) {
    my ($start_time, $base_start_time, $ts_clients) = @_;
    my ($start) = ytime();
    timestamp("Returning client sync start time, sync start time, sync sent time");
    foreach my $client (@$ts_clients) {
	my ($time) = ytime();
	my ($client_fd, $client_ts) = @$client;
	my ($tbuf) = "$client_ts $start_time $start $time $base_start_time";
	syswrite($client_fd, $tbuf, length $tbuf);
	close($client_fd);
    }
    my ($end) = ytime();
    my ($et) = $end - $start;
    timestamp("Sending sync time took $et seconds");
}

sub sync_one($$$$$$$) {
    my ($sock, $tmp_sync_file_base, $tmp_error_file, $start_time, $base_start_time, $expected_clients, $first_pass) = @_;
    timestamp("Listening on port $listen_port");
    listen($sock, $expected_clients) || die "listen: $!";
    printf STDERR "Expect $expected_clients client%s\n", $expected_clients == 1 ? '' : 's';
    my (@ts_clients);
    # Ensure that the client file descriptors do not get gc'ed,
    # closing it prematurely.  This is used when we don't
    # need to send a meaningful reply.
    # Tested with
    # clusterbuster -P synctest --synctest-count=10 --synctest-cluster-count=3 --precleanup
    #     --deployments=10 --cleanup=0 --pin-node=whatever
    my (@clients_protect_against_gc);
    while ($expected_clients > 0) {
	my ($client);
	accept($client, $sock) || next;
	my $peer = getpeername($client);
	my ($port, $addr) = sockaddr_in($peer);
	# Reverse hostname lookup adds significant overhead
	# when using sync to establish the timebase.
	#my $peerhost = gethostbyaddr($addr, AF_INET);
	my $peeraddr = inet_ntoa($addr);
	my ($tbuf) = read_token($client);
	if (! defined $tbuf) {
	    timestamp("Read token from $peeraddr failed: $!");
	}
	push @clients_protect_against_gc, $client;
	my ($command) = lc substr($tbuf, 0, 4);
	my ($payload_bytes) = length $tbuf - 4;
	timestamp("Accepted connection from $peeraddr on $port, command $command, payload $payload_bytes");
	$tbuf =~ s/^....\s+//;
	if ($command eq 'time')  {
	    my ($ignore, $ts, $ignore) = split(/ +/, $tbuf);
	    if (! $first_pass) {
		timestamp("Unexpected request for time sync from $tbuf!");
		open TMP, ">", "$tmp_error_file" || die ("Can't open error file $tmp_error_file: $!\n");
		print TMP "Unexpected request for time sync from $tbuf!";
		close TMP || die "Can't close error file: $!\n";
		link($tmp_error_file, $error_file) || die "Can't link $tmp_error_file to $error_file: $!\n";
		timestamp("Waiting for error file $error_file to be removed");
		while (-f $error_file) {
		    sleep(1);
		}
		POSIX::_exit(1)
	    }
	    push @ts_clients, [$client, "$ts " . ytime()];
	} elsif ($command eq 'rslt') {
	    handle_rslt($tmp_sync_file_base, $expected_clients, $tbuf);
	} elsif ($command eq 'fail') {
	    timestamp("Detected failure from $peeraddr");
	    if (defined $tmp_error_file) {
		open TMP, ">", "$tmp_error_file" || die("Can't open error file $tmp_error_file: $!\n");
		print TMP "$tbuf\n";
		close TMP || die "Can't close error file: $!\n";
		link($tmp_error_file, $error_file) || die "Can't link $tmp_error_file to $error_file: $!\n";
		timestamp("Waiting for error file $error_file to be removed");
		while (-f $error_file) {
		    sleep(1);
		}
	    } else {
		timestamp("Message: $tbuf");
	    }
	    POSIX::_exit(1);
	} elsif ($command eq 'sync') {
	    # No special handling needed for a normal sync
	} else {
	    timestamp("Unknown command from $peeraddr: '$command'");
	}
	$expected_clients--;
    }
    # Only reply to clients who provided a timestamp
    if (@ts_clients) {
	reply_timestamp($start_time, $base_start_time, @ts_clients);
    }
    timestamp("Sync complete");
    POSIX::_exit(0);
}

my ($start_time) = xtime();
my ($base_start_time) = $start_time;

$SIG{TERM} = sub { POSIX::_exit(0); };

my ($original_sync_count) = $sync_count;

timestamp("Clusterbuster sync starting");
my ($sock) = get_port($listen_port);

my ($tmp_sync_file_base) = (defined($sync_file) && $sync_file ne '') ? "${sync_file}-tmp" : undef;
my ($tmp_error_file) = (defined($error_file) && $error_file ne '') ? "${error_file}-tmp" : undef;

my (@tmp_sync_files) = map { "${tmp_sync_file_base}-$_" } (1..$expected_clients);

my ($controller_timestamp_data) = get_controller_timing($controller_timestamp_file);
timestamp("About to adjust timestamp");
timestamp(sprintf("Max timebase error %f" , $$controller_timestamp_data{'offset_from_controller'}));
$start_time += $$controller_timestamp_data{'offset_from_controller'};
timestamp("Adjusted timebase by $$controller_timestamp_data{'offset_from_controller'} seconds $base_start_time => $start_time");
timestamp("Will sync $sync_count times");
if ($sync_count == 0) {
    timestamp("No synchronization requested; sleeping $postdelay seconds");
    sleep($postdelay);
} else {
    my ($first_pass) = 1;
    while ($sync_count < 0 || $sync_count-- > 0) {
	if (-e $tmp_error_file) {
	    timestamp("Job failed, exiting");
	    exit(1);
	}
	my ($tmp_sync_file) = undef;
	# Ensure that all of the accepted connections get closed by exiting
	# a child process.  This way we don't have to keep track of all of the
	# clients and close them manually.
	my $child = fork();
	if ($child == 0) {
	    sync_one($sock, $tmp_sync_file_base, $tmp_error_file, $start_time, $base_start_time, $first_pass ? $initial_expected_clients : $expected_clients, $first_pass);
	} elsif ($child < 1) {
	    timestamp("Fork failed: $!");
	    POSIX::_exit(1);
	} else {
	    wait();
	}
	if ($first_pass) {
	    touch("/tmp/clusterbuster-started");
	    if ($predelay > 0) {
		timestamp("Waiting $predelay seconds before start");
		sleep($predelay);
	    }
	    $first_pass = 0;
	}
    }
    touch("/tmp/clusterbuster-finished");
    if ($postdelay > 0) {
	timestamp("Waiting $postdelay seconds before end");
	sleep($postdelay);
    }
}

if (-e $tmp_error_file) {
    timestamp("Job failed, exiting!");
    POSIX::_exit(1);
}
my (%result);
$result{'controller_timing'} = $controller_timestamp_data;
my (@data);

if (@tmp_sync_files) {
    foreach my $file (@tmp_sync_files) {
	if (-f $file && open FILE, "<", $file) {
	    my ($datum) = "";
	    while (<FILE>) {
		$datum .= $_;
	    }
	    close FILE;
	    push @data, from_json($datum);
	} else {
	    push @data, {};
	}
    }
} elsif ($original_sync_count == 0) {
    @data = map { {} } (1..$expected_clients);
    timestamp("here");
    timestamp(join("|", @data));
} else {
    timestamp("orig sync count $original_sync_count");
}
$result{'worker_results'} = \@data;

open (TMP, ">", $tmp_sync_file_base) || die "Can't open sync file $tmp_sync_file_base: $!\n";
print TMP to_json(clean_numbers(\%result));
close TMP || die "Can't close temporary sync file: $!\n";
rename($tmp_sync_file_base, $sync_file) || die "Can't rename $tmp_sync_file_base to $sync_file: $!\n";
timestamp("Waiting for sync file $sync_file to be removed");
while (-f $sync_file) {
    sleep(1);
}
timestamp("Sync file $sync_file removed, exiting");

POSIX::_exit(0);
EOF
