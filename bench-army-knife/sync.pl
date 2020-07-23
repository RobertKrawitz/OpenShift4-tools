#!/usr/bin/perl
use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday);
$SIG{TERM} = sub { POSIX::_exit(0); };
my ($listen_port, $expected_clients, $syncCount) = @ARGV;
if (! $syncCount) {
    $syncCount = 1;
}
sub timestamp(@) {
    my ($str) = join(" ", @_);
    my (@now) = gettimeofday();
    printf STDERR  "sync $$ %s.%06d %s\n", gmtime($now[0])->strftime("%Y-%m-%dT%T"), $now[1], $str;
}
timestamp("Clusterbuster sync starting");
my $sockaddr = "S n a4 x8";
socket(SOCK, AF_INET, SOCK_STREAM, getprotobyname('tcp')) || die "socket: $!";
$SIG{TERM} = sub { close SOCK; POSIX::_exit(0); };
setsockopt(SOCK,SOL_SOCKET, SO_REUSEADDR, pack("l",1)) || die "setsockopt reuseaddr: $!\n";
setsockopt(SOCK,SOL_SOCKET, SO_KEEPALIVE, pack("l",1)) || die "setsockopt keepalive: $!\n";
bind(SOCK, pack($sockaddr, AF_INET, $listen_port, "\0\0\0\0")) || die "bind: $!\n";
listen(SOCK, 5) || die "listen: $!";
my $mysockaddr = getsockname(SOCK);
my ($junk, $port, $addr) = unpack($sockaddr, $mysockaddr);
die "can't get port $port: $!\n" if ($port ne $listen_port);
timestamp("Listening on port $listen_port");
my (@clients);

while ($syncCount < 0 || $syncCount-- > 0) {
    my $child = fork();
    if ($child == 0) {
	print STDERR "Expect $expected_clients clients\n";
	while ($expected_clients > 0) {
	    my ($client);
	    timestamp("In client loop");
	    accept($client, SOCK) || next;
	    my $peeraddr = getpeername($client);
	    my ($port, $addr) = sockaddr_in($peeraddr);
	    timestamp("Accepted connection from " . inet_ntoa($addr));
	    my $peerhost = gethostbyaddr($addr, AF_INET);
	    my $peeraddr = inet_ntoa($addr);
	    timestamp("Accepted connection from $peerhost ($peeraddr) on $port");
	    print "$peeraddr\n";
	    my ($tbuf) = "NULL";
	    if (sysread($client, $tbuf, 1024) <= 0) {
		timestamp("Read token from $peerhost failed: $!");
	    }
	    timestamp("Accepted connection from $peerhost ($peeraddr) on $port, token $tbuf");
	    push @clients, $client;
	    $expected_clients--;
	}
	# Make sure that we're closed when we release the clients
	# so if they immediately try to sync again they won't inadvertently connect.
	close SOCK;
	timestamp("Waiting 1 second to sync:");
	sleep(1);
	timestamp("Done!");
	exit(0);
    } elsif ($child < 1) {
        timestamp("Fork failed: $!");
	exit(1);
    } else {
        wait();
    }
}

