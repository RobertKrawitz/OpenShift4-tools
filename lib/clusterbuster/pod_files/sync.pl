#!/usr/bin/perl
use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday usleep);
use JSON;
my ($verbose, $sync_file, $controller_timestamp_file);
my ($offset_from_controller) = 0;
use Getopt::Long;
Getopt::Long::Configure("bundling", "no_ignore_case", "pass_through");
GetOptions("v!"  => \$verbose,
	   "t:s" => \$controller_timestamp_file,
	   "f:s" => \$sync_file);
my ($dir) = $ENV{'BAK_CONFIGMAP'};
require "$dir/clientlib.pl";
my ($start_time) = xtime();
my ($base_start_time) = $start_time;

$SIG{TERM} = sub { POSIX::_exit(0); };
my ($listen_port, $expected_clients, $sync_count) = @ARGV;
if (! $sync_count) {
    $sync_count = 1;
}
sub ytime() {
    return xtime() + $offset_from_controller;
}
sub timestamp1($) {
    my ($str) = @_;
    my (@now) = POSIX::modf(ytime());
    printf STDERR  "sync %s.%06d %s\n", gmtime(int($now[1]))->strftime("%Y-%m-%dT%T"), $now[0], $str;
}
timestamp1("Clusterbuster sync starting");
my $sockaddr = "S n a4 x8";
socket(SOCK, AF_INET, SOCK_STREAM, getprotobyname('tcp')) || die "socket: $!";
$SIG{TERM} = sub { close SOCK; POSIX::_exit(0); };
setsockopt(SOCK,SOL_SOCKET, SO_REUSEADDR, pack("l",1)) || die "setsockopt reuseaddr: $!\n";
setsockopt(SOCK,SOL_SOCKET, SO_KEEPALIVE, pack("l",1)) || die "setsockopt keepalive: $!\n";
bind(SOCK, pack($sockaddr, AF_INET, $listen_port, "\0\0\0\0")) || die "bind: $!\n";
my $mysockaddr = getsockname(SOCK);
my ($junk, $port, $addr) = unpack($sockaddr, $mysockaddr);
die "can't get port $port: $!\n" if ($port ne $listen_port);

my ($tmp_sync_file_base) = (defined($sync_file) && $sync_file ne '') ? "${sync_file}-tmp" : undef;

my (@tmp_sync_files) = map { "${tmp_sync_file_base}-$_" } (1..$expected_clients);

sub read_token($) {
    my ($client) = @_;
    my ($tbuf) = '';
    if (sysread($client, $tbuf, 10) != 10) {
	timestamp1("Unable to read token");
	return undef;
    }
    if (!($tbuf =~ /0x[[:xdigit:]]{8}/)) {
	timestamp1("Bad token $tbuf!");
	return undef;
    }
    my ($bytes_to_read) = hex($tbuf);
    $tbuf = '';
    my ($offset) = 0;
    while ($bytes_to_read > 0) {
	my ($bytes) = sysread($client, $tbuf, $bytes_to_read, $offset);
	if ($bytes == 0) {
	    timestamp1("Short read: got zero bytes with $bytes_to_read left at $offset");
	    return undef;
	} elsif ($bytes < 0) {
	    timestamp1("Bad read with $bytes_to_read left at $offset: $!");
	    return undef;
	} else {
	    $bytes_to_read -= $bytes;
	    $offset += $bytes;
	}
    }
    return $tbuf
}

my ($first_pass) = 1;
timestamp1("Waiting to receive controller time data");
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
    $controller_timestamp_data = from_json($controller_json_data);
    timestamp1("About to adjust timestamp");
    $offset_from_controller = $$controller_timestamp_data{'second_controller_ts'} - $$controller_timestamp_data{'sync_ts'};
    $start_time += $offset_from_controller;
    timestamp1("Adjusted timebase by $offset_from_controller seconds $base_start_time => $start_time");
    timestamp1(sprintf("Max timebase error %f" , $$controller_timestamp_data{'second_controller_ts'} - $$controller_timestamp_data{'first_controller_ts'}));
    unlink($controller_timestamp_file);
}
while ($sync_count < 0 || $sync_count-- > 0) {
    my ($tmp_sync_file) = undef;
    # Ensure that all of the accepted connections get closed by exiting
    # a child process.  This way we don't have to keep track of all of the
    # clients and close them manually.
    my $child = fork();
    if ($child == 0) {
	timestamp1("Listening on port $listen_port");
	listen(SOCK, 5) || die "listen: $!";
	print STDERR "Expect $expected_clients clients\n";
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
		timestamp1("Read token from $peeraddr  failed: $!");
	    }
	    timestamp1("Accepted connection from $peeraddr on $port, token $tbuf");
	    if (substr($tbuf, 0, 10) eq 'timestamp:')  {
		my ($ignore, $ts, $ignore) = split(/ +/, $tbuf);
		push @clients, [$client, "$ts " . ytime()];
	    } elsif ($tbuf =~ /clusterbuster-json/ && defined $tmp_sync_file_base) {
		$tmp_sync_file = sprintf("%s-%d", $tmp_sync_file_base, $expected_clients);
		chomp $tbuf;
		open TMP, ">", "$tmp_sync_file" || die("Can't open sync file $tmp_sync_file: $!\n");
		print TMP "$tbuf\n";
		close TMP || die "Can't close sync file: $!\n";
	    } else {
		push @clients_protect_against_gc, $client;
	    }
	    $expected_clients--;
	}
	timestamp1("Done!");
	my ($first_time, $last_time);
	my ($start) = ytime();
	# Only reply to clients who provided a timestamp
	my (@ts_msgs) = ();
	if (@clients) {
	    timestamp1("Returning client sync start time, sync start time, sync sent time");
	    foreach my $client (@clients) {
		my ($time) = ytime();
		my ($client_fd, $client_ts) = @$client;
		my ($tbuf) = "$client_ts $start_time $start $time $base_start_time";
		syswrite($client_fd, $tbuf, length $tbuf);
		close($client_fd);
	    }
	    my ($end) = ytime();
	    my ($et) = $end - $start;
	    timestamp1("Sending sync time took $et seconds");
	}
        POSIX::_exit(0);
    } elsif ($child < 1) {
        timestamp1("Fork failed: $!");
	POSIX::_exit(1);
    } else {
        wait();
    }
    $first_pass = 0;
}
if (@tmp_sync_files) {
    my ($tmp_sync_file) = "${tmp_sync_file_base}";
    open (TMP, ">", $tmp_sync_file) || die "Can't open sync file $tmp_sync_file: $!\n";
    my (%result);
    my (@data);
    foreach my $file (@tmp_sync_files) {
	-f $file || next;
	open FILE, "<", $file || next;
	my ($datum) = "";
	while (<FILE>) {
	    $datum .= $_;
	}
	close FILE;
	push @data, from_json($datum);
    }
    $result{'controller_timing'} = $controller_timestamp_data;
    $result{'worker_results'} = \@data;
    print TMP to_json(\%result);
    close TMP || die "Can't close temporary sync file: $!\n";
    rename($tmp_sync_file, $sync_file) || die "Can't rename $sync_file to $tmp_sync_file: $!\n";
    timestamp1("Waiting for sync file $sync_file to be removed");
    while (-f $sync_file) {
	sleep(5);
    }
    timestamp1("Sync file $sync_file removed, exiting");
}

POSIX::_exit(0);
EOF
