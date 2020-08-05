#!/usr/bin/perl
use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday);

my ($addr, $port, $token) = @ARGV;
if ($addr eq '' || $addr eq '-') {
    $addr=`ip route get 1 |awk '{print \$(NF-2); exit}'`;
    chomp $addr;
}
#my ($alt_addr) =`ip route get 1 |awk '{print \$3; exit}'`;
#chomp $alt_addr;
sub timestamp($) {
    my ($str) = @_;
    my (@now) = gettimeofday();
    printf STDERR  "sync_to $$ %s.%06d %s\n", gmtime($now[0])->strftime("%Y-%m-%dT%T"), $now[1], $str;
}
if (not $addr) {
    die "No address provided!\n";
}
if (not $token) {
    $token = sprintf('%d', rand() * 999999999);
}

sub connect_to($$) {
    my ($port, $addr) = @_;
    my ($connected) = 0;
    my ($fname,$faliases,$ftype,$flen,$faddr);
    my ($sock);
    my ($iteration) = 0;
    do {
        ($fname,$faliases,$ftype,$flen,$faddr) = gethostbyname($addr);
        my $sockaddr = "S n a4 x8";
        if (length($faddr) < 4) {
            print STDERR "Malformed address, waiting for addr for $addr\n";
            sleep(1);
        } else {
            my $straddr = inet_ntoa($faddr);
            timestamp("Connecting to $addr:$port ($fname, $ftype)");
            my $sockmeta = pack($sockaddr, AF_INET, $port, $faddr);
            socket($sock, AF_INET, SOCK_STREAM, getprotobyname('tcp')) || die "can't make socket: $!";
            if (connect($sock, $sockmeta)) {
                $connected = 1;
                timestamp("Connected to $addr:$port ($fname, $ftype), waiting for sync");
            } else {
                timestamp("Could not connect to $addr on port $port: $!");
                close $sock;
                sleep(1);
            }
        }
    } while (! $connected);
    return ($sock);
}

while (1) {
    timestamp("Waiting for sync on $addr:$port");
    my ($_conn, $i1, $i2) = connect_to($port, $addr);
    my ($sbuf);
    timestamp("Writing token $token to sync");
    my ($answer) = syswrite($_conn, $token, length $token);
    if ($answer != length $token) {
	timestamp("Write token failed: $!");
	exit(1);
    }
    $answer = sysread($_conn, $sbuf, 1024);
    my ($str) = sprintf("Got sync (%s, %s, %s)!", $answer, $sbuf, $!);
    print $sbuf;
    if ($!) {
	timestamp("$str, retrying");
    } else {
	timestamp("$str");
	exit(0);
    }
}
