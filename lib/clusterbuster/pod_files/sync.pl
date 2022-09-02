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
	my (@answer) = map {clean_numbers($_)} @$ref;;
	return \@answer;
    } elsif (ref $ref eq '' && looks_like_number($ref) && $ref != 0 &&
	     (! defined ($ref <=> 0) || ((1 / $ref) == 0))) {
	return undef;
    } else {
	return $ref
    }
}

sub to_json_safe($) {
    my ($ref) = @_;
    return to_json(clean_numbers($ref));
}

my ($start_time) = xtime();
my ($base_start_time) = $start_time;

$SIG{TERM} = sub { POSIX::_exit(0); };
my ($listen_port, $expected_clients, $sync_count) = @ARGV;
my ($original_sync_count) = $sync_count;
sub ytime() {
    return xtime() + $offset_from_controller;
}
sub timestamp($) {
    my ($str) = @_;
    my (@now) = POSIX::modf(ytime());
    printf STDERR  "sync %s.%06d %s\n", gmtime(int($now[1]))->strftime("%Y-%m-%dT%T"), $now[0] * 1000000, $str;
}
timestamp("Clusterbuster sync starting");
if ($sync_count > 0) {
    my $sockaddr = "S n a4 x8";
    socket(SOCK, AF_INET, SOCK_STREAM, getprotobyname('tcp')) || die "socket: $!";
    $SIG{TERM} = sub { close SOCK; POSIX::_exit(0); };
    setsockopt(SOCK,SOL_SOCKET, SO_REUSEADDR, pack("l",1)) || die "setsockopt reuseaddr: $!\n";
    setsockopt(SOCK,SOL_SOCKET, SO_KEEPALIVE, pack("l",1)) || die "setsockopt keepalive: $!\n";
    bind(SOCK, pack($sockaddr, AF_INET, $listen_port, "\0\0\0\0")) || die "bind: $!\n";
    my $mysockaddr = getsockname(SOCK);
    my ($junk, $port, $addr) = unpack($sockaddr, $mysockaddr);
    die "can't get port $port: $!\n" if ($port ne $listen_port);
}

my ($tmp_sync_file_base) = (defined($sync_file) && $sync_file ne '') ? "${sync_file}-tmp" : undef;
my ($tmp_error_file) = (defined($error_file) && $error_file ne '') ? "${error_file}-tmp" : undef;

my (@tmp_sync_files) = map { "${tmp_sync_file_base}-$_" } (1..$expected_clients);

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

my ($first_pass) = 1;
timestamp("Waiting to receive controller time data");
my ($controller_timestamp_data);
my ($controller_offset_from_sync);
if ($controller_timestamp_file) {
    while (! -f $controller_timestamp_file) {
	sleep(1);
    }
    open TIMESTAMP, "<", $controller_timestamp_file || die "Can't open timestamp file $controller_timestamp_file: $!\n";
    my ($controller_json_data) = "";
    while (<TIMESTAMP>) {
	$controller_json_data .= $_;
    }
    close TIMESTAMP;
    timestamp("Timestamp data: $controller_json_data");
    $controller_timestamp_data = from_json($controller_json_data);
    timestamp("About to adjust timestamp");
    $offset_from_controller = $$controller_timestamp_data{'second_controller_ts'} - $$controller_timestamp_data{'sync_ts'};
    $start_time += $offset_from_controller;
    timestamp("Adjusted timebase by $offset_from_controller seconds $base_start_time => $start_time");
    timestamp(sprintf("Max timebase error %f" , $$controller_timestamp_data{'second_controller_ts'} - $$controller_timestamp_data{'first_controller_ts'}));
    unlink($controller_timestamp_file);
}
timestamp("Will sync $sync_count times");
if ($sync_count == 0) {
    timestamp("No synchronization requested; sleeping $postdelay seconds");
    sleep($postdelay);
} else {
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
	    timestamp("Listening on port $listen_port");
	    listen(SOCK, 5) || die "listen: $!";
	    printf STDERR "Expect $expected_clients client%s\n", $expected_clients == 1 ? '' : 's';
	    my (@clients);
	    # Ensure that the client file descriptors do not get gc'ed,
	    # closing it prematurely.  This is used when we don't
	    # need to send a meaningful reply.
	    # Tested with
	    # clusterbuster -P synctest --synctest-count=10 --synctest-cluster-count=3 --precleanup
	    #     --deployments=10 --cleanup=0 --pin-node=whatever
	    my (@clients_protect_against_gc);
	    while ($expected_clients > 0) {
		my ($client);
		accept($client, SOCK) || next;
		my $peeraddr = getpeername($client);
		my ($port, $addr) = sockaddr_in($peeraddr);
		# Reverse hostname lookup adds significant overhead
		# when using sync to establish the timebase.
		#my $peerhost = gethostbyaddr($addr, AF_INET);
		my $peeraddr = inet_ntoa($addr);
		my ($tbuf) = read_token($client);
		if (! defined $tbuf) {
		    timestamp("Read token from $peeraddr  failed: $!");
		}
		timestamp("Accepted connection from $peeraddr on $port, token $tbuf");
		push @clients_protect_against_gc, $client;
		if (substr($tbuf, 0, 10) eq 'timestamp:')  {
		    my ($ignore, $ts, $ignore) = split(/ +/, $tbuf);
		    push @clients, [$client, "$ts " . ytime()];
		} elsif ($tbuf =~ /clusterbuster-json/ && defined $tmp_sync_file_base) {
		    $tmp_sync_file = sprintf("%s-%d", $tmp_sync_file_base, $expected_clients);
		    chomp $tbuf;
		    open TMP, ">", "$tmp_sync_file" || die("Can't open sync file $tmp_sync_file: $!\n");
		    print TMP "$tbuf\n";
		    close TMP || die "Can't close sync file: $!\n";
		} elsif ($tbuf =~ /^[-[:digit:]T:.]* FAIL:/ && defined $tmp_error_file) {
		    timestamp("Detected failure!");
		    open TMP, ">", "$tmp_error_file" || die("Can't open error file $tmp_error_file: $!\n");
		    print TMP "$tbuf\n";
		    close TMP || die "Can't close error file: $!\n";
		    link($tmp_error_file, $error_file) || die "Can't link $tmp_error_file to $error_file: $!\n";
		    timestamp("Waiting for error file $error_file to be removed");
		    while (-f $error_file) {
			sleep(5);
		    }
		    POSIX::_exit(1);
		}
		$expected_clients--;
	    }
	    timestamp("Done!");
	    if ($first_pass) {
		`touch /tmp/clusterbuster-started`;
		if ($predelay > 0) {
		    timestamp("Waiting $predelay seconds before start");
		    sleep($predelay);
		}
	    } elsif ($sync_count == 0) {
		`touch /tmp/clusterbuster-finished`;
		if ($postdelay > 0) {
		    timestamp("Waiting $postdelay seconds before end");
		    sleep($postdelay);
		}
	    }
	    my ($first_time, $last_time);
	    my ($start) = ytime();
	    # Only reply to clients who provided a timestamp
	    my (@ts_msgs) = ();
	    if (@clients) {
		timestamp("Returning client sync start time, sync start time, sync sent time");
		foreach my $client (@clients) {
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
	    timestamp("Sync complete, about to exit");
	    POSIX::_exit(0);
	} elsif ($child < 1) {
	    timestamp("Fork failed: $!");
	    POSIX::_exit(1);
	} else {
	    wait();
	}
	$first_pass = 0;
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
print TMP to_json_safe(\%result);
close TMP || die "Can't close temporary sync file: $!\n";
rename($tmp_sync_file_base, $sync_file) || die "Can't rename $tmp_sync_file_base to $sync_file: $!\n";
timestamp("Waiting for sync file $sync_file to be removed");
while (-f $sync_file) {
    sleep(5);
}
timestamp("Sync file $sync_file removed, exiting");

POSIX::_exit(0);
EOF
