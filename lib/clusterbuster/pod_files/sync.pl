#!/usr/bin/perl
use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday usleep);
my ($verbose, $sync_file);
use Getopt::Long;
Getopt::Long::Configure("bundling", "no_ignore_case", "pass_through");
GetOptions("v!"  => \$verbose,
	   "f:s" => \$sync_file);
my ($dir) = $ENV{'BAK_CONFIGMAP'};
require "$dir/clientlib.pl";
my ($start_time) = xtime();

$SIG{TERM} = sub { POSIX::_exit(0); };
my ($listen_port, $expected_clients, $sync_count) = @ARGV;
if (! $sync_count) {
    $sync_count = 1;
}
sub timestamp($) {
    my ($str) = @_;
    my (@now) = gettimeofday();
    printf STDERR  "sync %s.%06d %s\n", gmtime($now[0])->strftime("%Y-%m-%dT%T"), $now[1], $str;
}
timestamp("Clusterbuster sync starting");
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
while ($sync_count < 0 || $sync_count-- > 0) {
    my ($tmp_sync_file) = undef;
    # Ensure that all of the accepted connections get closed by exiting
    # a child process.  This way we don't have to keep track of all of the
    # clients and close them manually.
    my $child = fork();
    if ($child == 0) {
	timestamp("Listening on port $listen_port");
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
		timestamp("Read token from $peeraddr  failed: $!");
	    }
	    timestamp("Accepted connection from $peeraddr on $port, token $tbuf");
	    if (substr($tbuf, 0, 10) eq 'timestamp:')  {
		my ($ignore, $ts, $ignore) = split(/ +/, $tbuf);
		push @clients, [$client, "$ts " . xtime()];
		if ($ts < $start_time) {
		    $start_time = $ts;
		}
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
	timestamp("Done!");
	my ($first_time, $last_time);
	my ($start) = xtime();
	# Only reply to clients who provided a timestamp
	my (@ts_msgs) = ();
	if (@clients) {
	    timestamp("Returning client sync start time, sync start time, sync sent time");
	    foreach my $client (@clients) {
		my ($time) = xtime();
		my ($client_fd, $client_ts) = @$client;
		my ($tbuf) = "$client_ts $start_time $start $time";
		syswrite($client_fd, $tbuf, length $tbuf);
		close($client_fd);
	    }
	    my ($end) = xtime();
	    my ($et) = $end - $start;
	    timestamp("Sending sync time took $et seconds");
	}
        POSIX::_exit(0);
    } elsif ($child < 1) {
        timestamp("Fork failed: $!");
	POSIX::_exit(1);
    } else {
        wait();
    }
    $first_pass = 0;
}
if (@tmp_sync_files) {
    my ($tmp_sync_file) = "${tmp_sync_file_base}";
    open (TMP, ">", $tmp_sync_file) || die "Can't open sync file $tmp_sync_file: $!\n";
    my (@data);
    foreach my $file (@tmp_sync_files) {
	-f $file || next;
	open FILE, "<", $file || next;
	my ($datum) = "";
	while (<FILE>) {
	    $datum .= $_;
	}
	close FILE;
	push @data, $datum;
    }
    print TMP join(",", @data);
    close TMP || die "Can't close temporary sync file: $!\n";
    rename($tmp_sync_file, $sync_file) || die "Can't rename $sync_file to $tmp_sync_file: $!\n";
    timestamp("Waiting for sync file $sync_file to be removed");
    while (-f $sync_file) {
	sleep(5);
    }
    timestamp("Sync file $sync_file removed, exiting");
}

POSIX::_exit(0);
EOF