#!/usr/bin/perl

use Time::HiRes qw(gettimeofday usleep);
use Time::Piece;
use File::Temp qw(:POSIX);

sub cputime() {
    my (@times) = times();
    my ($usercpu) = $times[0] + $times[2];
    my ($syscpu) = $times[1] + $times[3];
    return ($usercpu, $syscpu);
}

sub ts() {
    my (@now) = gettimeofday();
    return sprintf("%s.%06d", gmtime($now[0])->strftime("%Y-%m-%dT%T"), $now[1]);
}
sub timestamp($) {
    my ($str) = @_;
    printf STDERR "%7d %s %s\n", $$, ts(), $str;
}

sub xtime() {
    my (@now) = gettimeofday();
    return $now[0] + ($now[1] / 1000000.0);
}

sub calibrate_time() {
    for (my $i = 0; $i < 1000; $i++) {
        my ($start) = xtime();
	my ($end) = xtime();
	$time_overhead += $end - $start;
    }
    $time_overhead /= 1000;
}

sub connect_to($$) {
    my ($addr, $port) = @_;
    my ($connected) = 0;
    my ($ghbn_time, $stime);
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
            timestamp("Connecting to $addr:$port ($fname, $ftype)");
            $ghbn_time = xtime();
            my $sockmeta = pack($sockaddr, AF_INET, $port, $faddr);
            socket($sock, AF_INET, SOCK_STREAM, getprotobyname('tcp')) || die "can't make socket: $!";
            $stime = xtime();
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

# Configmaps are mounted noexec, so we have to copy sync_to somewhere that is executable.
if (! -f "/var/tmp/sync_to.pl") {
    open(COPYIN, "<", $ENV{'BAK_CONFIGMAP'} . "/sync_to.pl") || die "Can't open sync_to.pl to copy out: $!\n";
    open(COPYOUT, ">", "/var/tmp/sync_to.pl") || die "Can't open /var/tmp/sync_to.pl to copy in: $!\n";
    while (<COPYIN>) {
	print COPYOUT;
    }
    close(COPYIN);
    close(COPYOUT) || die "Can't close /var/tmp/sync_to.pl: $!\n";
    chmod(0555, "/var/tmp/sync_to.pl") || die "Can't chmod sync_to.pl: $!\n";
}

sub do_sync($$;$) {
    my ($addr, $port, $token) = @_;
    if (not $addr) { return; }
    my ($fh) = undef;
    my ($file) = undef;

    if ($addr eq '-') {
	$addr=`ip route get 1 |awk '{print \$(NF-2); exit}'`;
	chomp $addr;
    }
    if ($token && $token =~ /clusterbuster-json/) {
	$token =~ s,\n *,,g;
    } elsif (not $token) {
        $token = sprintf('%s-%d', $pod, rand() * 999999999);
    }
    if (length $token > 64) {
	($fh, $file) = tmpnam();
	print $fh $token;
	close $fh;
    }
    my $fh;
    if (defined $file) {
	open($fh, "-|", "/var/tmp/sync_to.pl", "-t", $file, $addr, $port) || die "Can't sync: $!\n";
    } else {
	open($fh, "-|", "/var/tmp/sync_to.pl", $addr, $port, $token) || die "Can't sync: $!\n";
    }
    my ($answer);
    while (<$fh>) {
	$answer .= $_;
    }
    if (! close $fh) {
	if ($? == 0) {
	    timestamp("Sync failed: $?");
	}
    }
    return $answer;
}

sub run_cmd_to_stderr(@) {
    my (@cmd) = @_;
    timestamp("@cmd output");
    if (open(my $fh, "-|", @cmd)) {
	while (<$fh>) {
	    print STDERR "$cmd[0] $_";
	}
	close($fh)
    } else {
	timestamp("Can't run $cmd[0]");
    }
}

sub finish($) {
    my ($exit_at_end) = @_;
    run_cmd_to_stderr("lscpu");
    run_cmd_to_stderr("dmesg");
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

1;
