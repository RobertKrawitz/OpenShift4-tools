#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday usleep);
use Sys::Hostname;
use File::Basename;
use JSON;
$SIG{TERM} = sub { POSIX::_exit(0); };
require "clientlib.pl";

my ($listen_port) = @ARGV;

my ($pod) = hostname;

timestamp("Cache drop starting");
my $sockaddr = "S n a4 x8";
socket(SOCK, AF_INET, SOCK_STREAM, getprotobyname('tcp')) || die "socket: $!";
$SIG{TERM} = sub { close SOCK; kill 'KILL', -1; POSIX::_exit(0); };
setsockopt(SOCK,SOL_SOCKET, SO_REUSEADDR, pack("l",1)) || die "setsockopt reuseaddr: $!\n";
setsockopt(SOCK,SOL_SOCKET, SO_KEEPALIVE, pack("l",1)) || die "setsockopt keepalive: $!\n";
bind(SOCK, pack($sockaddr, AF_INET, $listen_port, "\0\0\0\0")) || die "bind: $!\n";
listen(SOCK, 5) || die "listen: $!";
my $mysockaddr = getsockname(SOCK);
my ($junk, $port, $addr) = unpack($sockaddr, $mysockaddr);
die "can't get port $port: $!\n" if ($port ne $listen_port);
timestamp("Listening on port $listen_port");
$SIG{CHLD} = 'IGNORE';

while (1) {
    accept(CLIENT, SOCK) || next;
    my $peeraddr = getpeername(CLIENT);
    my ($port, $addr) = sockaddr_in($peeraddr);
    my $peerhost = gethostbyaddr($addr, AF_INET);
    my $peeraddr = inet_ntoa($addr);
    timestamp("Accepted connection from $peerhost ($peeraddr) on $port!");
    timestamp("About to sync()...");
    system("sync");
    timestamp("About to drop cache...");
    if (open(my $fh, '>', '/proc/sys/vm/drop_caches')) {
	print $fh '3';
	if (close $fh) {
	    timestamp("Successfully dropped cache:");
	} else {
	    timestamp("Can't close /proc/sys/vm/drop_caches: $!");
	}
    } else {
	timestamp("Can't open /proc/sys/vm/drop_caches: $!");
    }
    close(CLIENT);
}
