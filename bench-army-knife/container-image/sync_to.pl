#!/usr/bin/perl
use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday);

my (@addrs);
my ($addr, $port, $token) = @ARGV;
if ($addr eq '' || $port eq '') {
    die "Usage: $0 addr port [token]\n";
}
print STDERR "addr is '$addr'\n";
if ($addr eq '' || $addr eq '-') {
    $addr=`ip route get 1 |awk '{print \$(NF-2); exit}'`;
    chomp $addr;
    my ($alt_addr) =`ip route get 1 |awk '{print \$3; exit}'`;
    chomp $alt_addr;
    @addrs = ($addr, $alt_addr);
} else {
    @addrs = ($addr);
    print STDERR "Using $addr from the command line\n";
}

sub xtime() {
    my (@now) = gettimeofday();
    return $now[0]+($now[1] / 1000000.0);
}

sub timestamp($) {
    my ($str) = @_;
    my (@now) = gettimeofday();
    printf STDERR  "sync_to $$ %s.%06d %s\n", gmtime($now[0])->strftime("%Y-%m-%dT%T"), $now[1], $str;
}
if (not $addr) {
    die "No address provided!\n";
}
if (not $token) {
    $token = sprintf('%d %s', rand() * 999999999, `hostname`);
    chomp $token;
}
timestamp("My token will be $token");

my ($initial_reporting_interval) = 60;
my ($max_reporting_interval) = 3600;

sub connect_to {
    my ($port, @addrs) = @_;
    timestamp("Using addresses " . join(", ", @addrs));
    my ($connected) = 0;
    my ($fname,$faliases,$ftype,$flen,$faddr);
    my ($sock);
    my ($iteration) = 0;
    my ($last_connecting_msg_reps) = 0;
    my ($last_connecting_msg_stamp) = -1;
    my ($last_connecting_msg);
    my ($last_failure_msg_reps) = 0;
    my ($last_failure_msg_stamp) = -1;
    my ($last_failure_msg);
    my ($reporting_interval) = $initial_reporting_interval;
    do {
	my ($addr) = $addrs[$iteration++ % ($#addrs + 1)];
        ($fname,$faliases,$ftype,$flen,$faddr) = gethostbyname($addr);
        my $sockaddr = "S n a4 x8";
        if (length($faddr) < 4) {
            print STDERR "Malformed address, waiting for addr for $addr\n";
            sleep(1);
        } else {
            my $straddr = inet_ntoa($faddr);
	    my $now = xtime;
	    my ($connecting_msg) = "Connecting to $addr:$port ($fname, $ftype)";
	    if ($connecting_msg ne $last_connecting_msg || $now - $last_connecting_msg_stamp >= $reporting_interval) {
		if ($connecting_msg eq $last_connecting_msg && $last_connecting_msg_reps > 0) {
		    timestamp("Last message repeated $last_connecting_msg_reps time" . ($last_connecting_msg_reps > 1 ? "s" : ""));
		    $reporting_interval *= 2;
		    if ($reporting_interval > $max_reporting_interval) {
			$reporting_interval = $max_reporting_interval;
		    }
		} else {
		    timestamp($connecting_msg);
		    $reporting_interval = $initial_reporting_interval;
		}
		$last_connecting_msg_stamp = $now;
		$last_connecting_msg_reps = 0;
		$last_connecting_msg = $connecting_msg;
	    }
            my $sockmeta = pack($sockaddr, AF_INET, $port, $faddr);
            socket($sock, AF_INET, SOCK_STREAM, getprotobyname('tcp')) || die "can't make socket: $!";
            if (connect($sock, $sockmeta)) {
                $connected = 1;
		if ($last_connecting_msg_reps > 1) {
		    timestamp("Last message repeated $last_connecting_msg_reps times");
		}
                timestamp("Connected to $addr:$port ($fname, $ftype), waiting for sync");
            } else {
		my ($failure_msg) = "Could not connect to $addr on port $port: $!";
		if ($failure_msg ne $last_failure_msg || $now - $last_failure_msg_stamp >= 60) {
		    if ($failure_msg eq $last_failure_msg && $last_failure_msg_reps > 0) {
			timestamp("Last message repeated $last_failure_msg_reps time" . ($last_failure_msg_reps > 1 ? "s" : ""));
		    } else {
			timestamp($failure_msg);
		    }
		    $last_failure_msg_stamp = $now;
		    $last_failure_msg_reps = 0;
		    $last_failure_msg = $failure_msg;
		}
		$last_failure_msg_reps++;
                close $sock;
                sleep(1);
            }
	    $last_connecting_msg_reps++;
        }
    } while (! $connected);
    return ($sock);
}

while (1) {
    timestamp("Waiting for sync on $addr:$port (" . join(", ", @addrs) . ")");
    my ($_conn, $i1, $i2) = connect_to($port, @addrs);
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
