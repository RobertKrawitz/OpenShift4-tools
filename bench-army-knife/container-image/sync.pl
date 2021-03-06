#!/usr/bin/perl
use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday);
use Getopt::Long;
Getopt::Long::Configure("bundling", "no_ignore_case", "pass_through");
my ($verbose) = 0;
GetOptions("v!" => \$verbose);

$SIG{TERM} = sub { POSIX::_exit(0); };
my ($listen_port, $expected_clients, $syncCount, @ssh_ports) = @ARGV;
if ($listen_port eq '' || $expected_clients eq '') {
    die "Usage: $0 listen_port expected_clients [count=1 [ssh_ports]]\n";
}
if (! $syncCount) {
    $syncCount = 1;
}
sub timestamp(@) {
    my ($str) = join(" ", @_);
    my (@now) = gettimeofday();
    printf STDERR  "sync $$ %s.%06d %s\n", gmtime($now[0])->strftime("%Y-%m-%dT%T"), $now[1], $str;
}
my $sockaddr = "S n a4 x8";
socket(SOCK, AF_INET, SOCK_STREAM, getprotobyname('tcp')) || die "socket: $!";
$SIG{TERM} = sub { close SOCK; POSIX::_exit(0); };
setsockopt(SOCK,SOL_SOCKET, SO_REUSEADDR, pack("l",1)) || die "setsockopt reuseaddr: $!\n";
setsockopt(SOCK,SOL_SOCKET, SO_KEEPALIVE, pack("l",1)) || die "setsockopt keepalive: $!\n";
bind(SOCK, pack($sockaddr, AF_INET, $listen_port, "\0\0\0\0")) || die "bind: $!\n";
my $mysockaddr = getsockname(SOCK);
my ($junk, $port, $addr) = unpack($sockaddr, $mysockaddr);
die "can't get port $port: $!\n" if ($port ne $listen_port);
my (@clients);

timestamp("Sync count will be $syncCount");
my $syncCount1 = 0;
while ($syncCount < 0 || $syncCount-- > 0) {
    my $child = fork();
    if ($child == 0) {
	timestamp("Listening on port $listen_port");
	listen(SOCK, 5) || die "listen: $!";
	timestamp("Pass $syncCount1 expect $expected_clients clients");
	$syncCount1++;
	while ($expected_clients > 0) {
	    my ($client);
	    accept($client, SOCK) || next;
	    my $peeraddr = getpeername($client);
	    my ($port, $addr) = sockaddr_in($peeraddr);
	    my $peerhost = gethostbyaddr($addr, AF_INET);
	    my $peeraddr = inet_ntoa($addr);
	    my ($tbuf) = "NULL";
	    if (sysread($client, $tbuf, 1024) <= 0) {
		timestamp("Read token from $peerhost failed: $!");
	    }
	    # Report the peer address out
	    if ($verbose) {
		print "$peeraddr $tbuf\n";
	    }
	    timestamp("Accepted connection from $peerhost ($peeraddr) on $port, token $tbuf");
	    push @clients, $client;
	    $expected_clients--;
	}
	foreach my $i (0..$#clients) {
	    if ($ssh_ports[$i]) {
		syswrite($clients[$i], $ssh_ports[$i], length $ssh_ports[$i]);
	    }
	}
	sleep(1);
	# Make sure that we're closed when we release the clients
	# so if they immediately try to sync again they won't inadvertently connect.
	close SOCK;
	timestamp("Done!");
	exit(0);
    } elsif ($child < 1) {
        timestamp("Fork failed: $!");
	exit(1);
    } else {
	close(SOCK);
        wait();
    }
}

