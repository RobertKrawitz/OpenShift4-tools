#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday usleep);
use File::Path qw(make_path remove_tree);
use Sys::Hostname;
use File::Basename;
use JSON;
my ($dir) = $ENV{'BAK_CONFIGMAP'};
require "$dir/clientlib.pl";

our ($namespace, $container, $basetime, $baseoffset, $crtime, $exit_at_end, $synchost, $syncport, $loghost, $logport,
     $processes, $rundir, $runtime, $jobfiles_dir, $fio_blocksizes, $fio_patterns, $fio_generic_args) = @ARGV;
my ($start_time) = xtime();

$SIG{TERM} = sub() { docleanup() };
$basetime += $baseoffset;
$crtime += $baseoffset;

my ($pod) = hostname;
my ($idname) = "$namespace:$pod:$container";

initialize_timing($basetime, $crtime, $synchost, $syncport, $idname, $start_time);

my ($localrundir);

sub removeRundir() {
    if (-d "$localrundir") {
	open(CLEANUP, "-|", "rm -rf '$localrundir'");
	while (<CLEANUP>) {
	    1;
	}
	close(CLEANUP);
    }
}

sub docleanup()  {
    print STDERR "CLEANUP\n";
    removeRundir();
    kill 'KILL', -1;
    POSIX::_exit(0);
}

sub runit(;$) {
    my ($jobfile) = @_;
    my ($firsttime) = 1;
    my ($avgcpu) = 0;
    my ($weight) = .25;
    my ($icputime);
    my ($interval) = 5;
    my ($data_start_time) = xtime();
    my (%all_results);
    my ($data_start_time);

    my (@sizes) = split(/ +/, $fio_blocksizes);
    my (@patterns) = split(/ +/, $fio_patterns);
    my ($ucpu0, $scpu0) = cputime();
    my ($jobidx) = 1;
    my ($elapsed_time) = 0;
    timestamp("Sizes: " . join(" ", @sizes));
    timestamp("Patterns: " . join(" ", @patterns));
    foreach my $size (@sizes) {
	foreach my $pattern (@patterns) {
	    my ($jobname) = sprintf("%03d-%s-%d", $jobidx, $pattern, $size);
	    do_sync($synchost, $syncport, "$namespace:$pod:$container:$$:$jobname");
	    if ($jobidx == 1) {
		timestamp("Running...");
		$data_start_time = xtime();
	    }
	    my ($answer0) = '';
	    timestamp("fio --rw=$pattern --bs=$size $fio_generic_args --output-format=json+ $jobfile");
	    my ($jtime0) = xtime();
	    my ($jucpu0, $jscpu0) = cputime();
	    open(RUN, "-|", "fio --rw=$pattern --bs=$size $fio_generic_args --output-format=json+ $jobfile | jq -c .") || die "Can't run fio: $!\n";
	    while (<RUN>) {
		$answer0 .= "$_";
	    }
	    close(RUN);
	    timestamp("Done job $jobfile $jobname");
	    my ($jtime1) = xtime();
	    my ($jucpu1, $jscpu1) = cputime();
	    my ($result) = from_json($answer0);
	    $jtime1 -= $jtime0;
	    $jucpu1 -= $jucpu0;
	    $jscpu1 -= $jscpu0;
	    $elapsed_time += $jtime1;
	    my (%job_result) = (
		'job_elapsed_time' => $jtime1,
		'job_user_cpu_time' => $jucpu1,
		'job_system_cpu_time' => $jscpu1,
		'job_cpu_time' => $jscpu1 + $jucpu1,
		'job_results' => $result
		);
	    $all_results{$jobname} = \%job_result;
	    $jobidx++;
	}
    }
    my ($data_end_time) = xtime();
    my ($ucpu1, $scpu1) = cputime();
    $ucpu1 -= $ucpu0;
    $scpu1 -= $scpu0;
    my (%extras) = (
	'results' => \%all_results
	);
    if (! ($jobfile =~ /-IGNORE-/)) {
	my ($answer) = print_json_report($namespace, $pod, $container, $$, $data_start_time,
					 $data_end_time, $elapsed_time, $ucpu1, $scpu1, \%extras);

	do_sync($synchost, $syncport, $answer);
	if ($logport > 0) {
	    do_sync($loghost, $logport, $answer);
	}
    }
}

sub get_jobfiles($$$) {
    my ($dir, $tmpdir, $localid) = @_;
    opendir DIR, $dir || die "Can't find job files in $dir: #!\n";

    my @files = map { "$dir/$_" } grep { -f "$dir/$_" } sort readdir DIR;
    closedir DIR;
    my (@nfiles) = ();
    foreach my $file (@files) {
	my ($nfile) = $file;
	if ($nfile =~ m,^(.*/)([^/]+)$,) {
	    $nfile = "${tmpdir}/$2";
	    timestamp("$file $1 $2 $nfile\n");
	    open READ_JOB, "<", "$file" || die "Can't open jobfile $file to read: $!\n";
	    open WRITE_JOB, ">", "$nfile" || die "Can't open temporary jobfile $file to write: $!\n";
	    while (<READ_JOB>) {
		chomp;
		timestamp($_);
		if (/^(\s*filename\s*=\s*)/) {
		    $_ .= "/$localid/$localid";
		}
		print WRITE_JOB "$_\n";
	    }
	    close READ_JOB;
	    close WRITE_JOB || die "Can't close temporary jobfile $file: $!\n";
	    push @nfiles, $nfile;
	}
    }
    print STDERR "get_jobfiles($dir) => @nfiles\n";
    return @nfiles;
}

sub runall() {
    my ($localid) = $idname . ":$$";
    $localid =~ s/:/_/g;
    $localrundir = "$rundir/$localid";
    my ($tmp_jobfilesdir) = "/tmp/fio-${localid}.job";
    mkdir "$tmp_jobfilesdir" || die "Can't create job directory $tmp_jobfilesdir: $!\n";

    removeRundir();

    if (! make_path($localrundir)) {
	timestamp("Cannot create run directory $localrundir: $!");
    }
    if (! chdir($localrundir)) {
	timestamp("Cannot cd $localrundir: $!");
	exit(1);
    }
    my (@jobfiles) = get_jobfiles($jobfiles_dir, $tmp_jobfilesdir, $localid);
    if ($#jobfiles >= 0) {
	foreach my $file (@jobfiles) {
	    runit($file);
	}
    } else {
        runit();
    }
    docleanup();
}

if ($processes > 1) {
    for (my $i = 0; $i < $processes; $i++) {
        if ((my $child = fork()) == 0) {
            runall();
            exit(0);
        }
    }
    wait();
} else {
    runall();
}

finish($exit_at_end);
