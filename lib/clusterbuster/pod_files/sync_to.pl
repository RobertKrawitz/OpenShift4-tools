#!/usr/bin/perl

use Socket;
use POSIX;
use Getopt::Long;

Getopt::Long::Configure("bundling", "no_ignore_case", "pass_through");
GetOptions("t:s" => \$token_file);
my ($dir) = $ENV{'BAK_CONFIGMAP'};
require "$dir/clientlib.pl";

my ($addr, $port, $token) = @ARGV;
if ($token_file) {
    if ($token_file eq '-') {
	while (<STDIN>) {
	    $token .= $_;
	}
    } else {
	open IN, $token_file || die "Can't open token file $token_file: $!\n";
	while (<IN>) {
	    $token .= $_;
	}
	close IN;
    }
}
	
if (not $addr) { exit 1; }
if ($addr eq '-') {
    $addr=`ip route get 1 |awk '{print \$(NF-2); exit}'`;
    chomp $addr;
}
if ($token && $token =~ /clusterbuster-json/) {
    $token =~ s,\n *,,g;
} elsif (not $token) {
    $token = sprintf('%s-%d', $pod, rand() * 999999999);
}
while (1) {
    timestamp("Waiting for sync on $addr:$port");
    my ($sync_conn) = connect_to($addr, $port);
    my ($sbuf);
    my ($token_length) = sprintf('0x%08x', length $token);
    my ($tbuf) = "$token_length$token";
    if (length $tbuf > 64) {
	timestamp("Writing $token_length to sync");
    } else {
	timestamp("Writing token $tbuf to sync");
    }
    my ($bytes_to_write) = length $tbuf;
    my ($offset) = 0;
    my ($answer);
    while ($bytes_to_write > 0) {
	$answer = syswrite($sync_conn, $tbuf, length $tbuf, $offset);
	if ($answer <= 0) {
	    timestamp("Write token failed: $!");
	    exit(1);
	} else {
	    $bytes_to_write -= $answer;
	    $offset += $answer;
	}
    }
    $answer = sysread($sync_conn, $sbuf, 1024);
    my ($str) = sprintf("Got sync (%s, %d, %s)!", $answer, length $sbuf, $!);
    if ($!) {
	timestamp("$str, retrying");
    } else {
	timestamp("$str, got sync");
	print("$str\n");
	exit(0);
    }
}
