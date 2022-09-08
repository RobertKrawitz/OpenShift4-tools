#!/usr/bin/perl

use POSIX;
use strict;
use File::Path qw(make_path remove_tree);
use JSON;
my ($dir) = $ENV{'BAK_CONFIGMAP'};
require "$dir/clientlib.pl";

my ($processes, $rundir, $runtime, $jobfiles_dir, $drop_cache_service, $drop_cache_port, $fio_blocksizes, $fio_patterns,
    $fio_iodepths, $fio_fdatasyncs, $fio_directs, $fio_ioengines, $fio_generic_args) = parse_command_line(@ARGV);

$SIG{TERM} = sub() { removeRundir() };

initialize_timing();

my ($localrundir);

sub removeRundir() {
    if (-d "$localrundir") {
	timestamp("Cleaning up run directory $localrundir");
	system('rm', '-rf', $localrundir);
    }
}

sub prepare_data_file($) {
    my ($jobfile) = @_;
    my ($filename);
    my ($filesize);
    open (my $job, '<', $jobfile) || die "Can't open job file: $!\n";
    while (<$job>) {
	chomp;
	if (/^\s*filename\s*=\s*(.+)/) {
	    $filename = $1;
	} elsif (/^\s*size\s*=\s*([[:digit:]]+)/) {
	    $filesize = $1;
	}
    }
    close $job;
    timestamp("  Job file $filename will be size $filesize");
    my ($blocksize) = 1048576;
    my ($blocks) = int(($filesize + 1048575) / $blocksize);
    my ($dirname) = $filename;
    $dirname =~ s,/[^/]*$,,;
    if (! -d $dirname) {
	system('mkdir', '-p', $dirname) || die "Can't create work directory $dirname: $!\n";
    }
    timestamp("Starting file creation");
    system('dd', 'if=/dev/zero', "of=$filename", 'bs=1048576', "count=$blocks");
    system("sync");
    timestamp("File created");
}

sub runone(;$) {
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
    my (@iodepths) = split(/ +/, $fio_iodepths);
    my (@fdatasyncs) = split(/ +/, $fio_fdatasyncs);
    my (@directs) = split(/ +/, $fio_directs);
    my (@ioengines) = split(/ +/, $fio_ioengines);
    my ($ucpu0, $scpu0) = cputime();
    my ($jobidx) = 1;
    my ($elapsed_time) = 0;
    timestamp("Sizes:       " . join(" ", @sizes));
    timestamp("Patterns:    " . join(" ", @patterns));
    timestamp("I/O depths:  " . join(" ", @iodepths));
    timestamp("Fdatasync:   " . join(" ", @fdatasyncs));
    timestamp("Direct I/O:  " . join(" ", @directs));
    timestamp("I/O engines: " . join(" ", @ioengines));
    timestamp("Creating workfile");
    prepare_data_file($jobfile);
    timestamp("Created workfile");
    foreach my $size (@sizes) {
	foreach my $pattern (@patterns) {
	    foreach my $iodepth (@iodepths) {
		foreach my $fdatasync (@fdatasyncs) {
		    foreach my $direct (@directs) {
			foreach my $ioengine (@ioengines) {
			    my ($jobname) = sprintf("%04d-%s-%d-%d-%d-%d-%s", $jobidx, $pattern, $size, $iodepth, $fdatasync, $direct, $ioengine);
			    drop_cache($drop_cache_service, $drop_cache_port);
			    sync_to_controller($$, $jobname);
			    if ($jobidx == 1) {
				timestamp("Running...");
				$data_start_time = xtime();
			    }
			    my ($answer0) = '';
			    timestamp("fio --rw=$pattern --runtime=$runtime --bs=$size --iodepth=$iodepth --fdatasync=$fdatasync --direct=$direct --ioengine=$ioengine $fio_generic_args --output-format=json+ $jobfile");
			    my ($jtime0) = xtime();
			    my ($jucpu0, $jscpu0) = cputime();
			    open(RUN, "-|", "fio --rw=$pattern --runtime=$runtime --bs=$size --iodepth=$iodepth --fdatasync=$fdatasync --direct=$direct --ioengine=$ioengine $fio_generic_args --output-format=json+ $jobfile | jq -c .") || die "Can't run fio: $!\n";
			    while (<RUN>) {
				timestamp($_);
				$answer0 .= "$_";
			    }
			    if (!close(RUN)) {
				timestamp("fio failed: $! $?");
				exit(1);
			    }
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
		}
	    }
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
	report_results($data_start_time, $data_end_time, $elapsed_time, $ucpu1, $scpu1, \%extras);
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

sub runit() {
    my ($localid) = idname('-s', $$);
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
	    runone($file);
	}
    } else {
        runone();
    }
    removeRundir();
}

run_workload($processes, \&runit);
