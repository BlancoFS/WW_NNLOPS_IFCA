import ROOT

import os
import sys
from sys import exit
from sys import argv
import linecache
import argparse
import time
import json
from pathlib import Path
import subprocess
import requests
from math import ceil

ROOT.gROOT.SetBatch(True)
ROOT.TH1.SetDefaultSumw2(True)

username = os.environ["USER"]
if username == "blancose":
    username = "sblancof"  ### Use CERN username for Sergio Blanco

run_1 = "HIG-RunIII2024Summer24MiniAODv6-00770_1_cfg.py"
run_2 = "HIG-RunIII2024Summer24NanoAODv15-00770_1_cfg.py"

campaign = "Summer24-NanoAODv15_0"
joblist  = "step1_filelist.txt"
fileOut  = "HIG-RunIII2024Summer24NanoAODv15-00770.root"
prefix   = f"/gpfs/projects/cms/sblancof/WWTo2L2Nu_Powheg_MiNNLO_13p6TeV/2024/{campaign}/"
redirector = ""

def defaultParser():
    parser = argparse.ArgumentParser(add_help=False)

    def list_of_strings(arg):
        return arg.split(',')

    parser.add_argument(
        "-s",
        "--doSubmit",
        type=int,
        choices=[0, 1],
        help="1: split and submit jobs to condor; 0: run interactively",
        required=False,
        default=0,
    )

    parser.add_argument(
        "-i",
        "--index",
        type=int,
        help="Index",
        required=False,
        default=-1,
    )

    parser.add_argument(
        "-nF",
        "--nFiles",
        type=int,
        help="Number of files to merge",
        required=False,
        default=-1,
    )

    return parser


def runLHEPRoduction(index=0, nFiles=1):

    fnames = []
    with open(joblist, 'r') as ffile:
        total_fnames = [line.strip().split(".root")[0]+".root" for line in ffile]
    fnames = total_fnames[index*nFiles:(index+1)*nFiles]
    
    ## Copy run script to TMPDIR
    tmp_dir = f"{os.environ['TMPDIR']}/{os.environ['USER']}/{campaign}_job_{index}"
    Path(tmp_dir).mkdir(parents=True, exist_ok=True)
    
    procString = f"cp {run_1} {tmp_dir}"
    proc = subprocess.run(procString,capture_output=True,text=True,shell=True)
    if proc.returncode != 0:
        print(proc.stderr)

    procString = f"cp {run_2} {tmp_dir}"
    proc = subprocess.run(procString,capture_output=True,text=True,shell=True)
    if proc.returncode != 0:
        print(proc.stderr)
        
    Path(prefix).mkdir(parents=True, exist_ok=True)
    
    os.chdir(tmp_dir)

    # Change input file in configuration 
    old = "'file:HIG-RunIII2024Summer24DRPremix-00770.root'"
    new = ",".join(f"'file:{fname}'" for fname in fnames)
    proc = subprocess.run(
        ["sed", "-i", f"s|{old}|{new}|g", run_1],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stderr)
    
    print("Running cmsRun MiniAOD...")
    print(f"Input files: \n")
    print(new)
    procString = f"cmsRun {run_1}"
    proc = subprocess.run(
        procString,
        capture_output=True,
        text=True,
        shell=True,
        #stdout=subprocess.PIPE,
        #stderr=subprocess.PIPE,
    )
    #out, err = proc.communicate()
    if proc.returncode != 0:
        print(f"ERROR: step-1 failed with exit code {proc.returncode}")
        # The fatal exception block is the useful part
        err = proc.stderr
        start = err.find("----- Begin Fatal Exception")
        if start != -1:
            end = err.find("----- End Fatal Exception", start)
            print(err[start:end + len("----- End Fatal Exception")])
        else:
            print("\n".join(err.splitlines()[-40:]))  # last 40 lines

        sys.exit(1)    

    print("Running cmsRun NanoAOD...")
    procString = f"cmsRun {run_2}"
    proc = subprocess.run(
        procString,
        capture_output=True,
        text=True,
        shell=True,
        #stdout=subprocess.PIPE,
        #stderr=subprocess.PIPE,
    )
    #out, err = proc.communicate()

    if proc.returncode != 0:
        print(f"ERROR: step-2 failed with exit code {proc.returncode}")
        # The fatal exception block is the useful part
        err = proc.stderr
        start = err.find("----- Begin Fatal Exception")
        if start != -1:
            end = err.find("----- End Fatal Exception", start)
            print(err[start:end + len("----- End Fatal Exception")])
        else:
            print("\n".join(err.splitlines()[-40:]))  # last 40 lines  
        sys.exit(1)
    
    tmpFile = fileOut.split(".root")[0] + f"_{index}.root"
    
    proc = subprocess.Popen(f"mv {fileOut} {prefix}/{tmpFile}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()    
            
def build_condor_submit(nFiles=1):

    with open(joblist, "r", encoding="utf-8") as f:
        line_count = sum(1 for line in f)

    ### Take into account the merging of files
    numJobs = max(ceil(float(line_count) / float(nFiles)), 1)
    
    print(f"Submitting {numJobs} jobs")

    slurmDir = os.path.abspath(os.getcwd())
    fSh = ""
    fSh += "#!/bin/sh \n"
    fSh += f"#SBATCH --job-name=WWTo2L2Nu_{campaign} \n"
    #fSh += "#SBATCH --partition=cloudcmsln \n"
    fSh += "#SBATCH --account=cms \n"
    fSh += "#SBATCH --cpus-per-task=1 \n"
    fSh += "#SBATCH --mem-per-cpu=8G \n"
    fSh += "#SBATCH --time=8:00:00   # equivalent to workday (adjust to your cluster) \n"
    fSh += f"#SBATCH --array=0-{numJobs} \n"
    fSh += "\n"
    #fSh += "export APPTAINER_BINDPATH=/afs,/cvmfs,/cvmfs/grid.cern.ch/etc/grid-security:/etc/grid-security,/cvmfs/grid.cern.ch/etc/grid-security/vomses:/etc/vomses,/gpfs,/etc/pki/ca-trust,/run/user,/tmp,/var/run/user,/etc/sysconfig,/etc:/orig/etc \n"
    #fSh += f"apptainer -s exec /cvmfs/unpacked.cern.ch/gitlab-registry.cern.ch/cms-cat/cmssw-lxplus/cmssw-el7-lxplus:latest/ {os.path.dirname(os.path.abspath(__file__))}/run.sh $SLURM_ARRAY_TASK_ID \n"
    fSh += f"{os.path.dirname(os.path.abspath(__file__))}/run_nano.sh $SLURM_ARRAY_TASK_ID \n"

    with open(f"{slurmDir}/submit_nano.jdl", "w") as file:
        file.write(fSh)

    runSh = "#!/bin/bash \n"
    runSh += " \n"
    runSh += f"cd {os.path.dirname(os.path.abspath(__file__))} \n"
    runSh += "source /cvmfs/cms.cern.ch/cmsset_default.sh \n"
    runSh += "cmsenv \n"
    runSh += "export X509_USER_PROXY=/gpfs/users/blancose/.proxy \n"
    runSh += " \n"
    runSh += "echo $1 \n"
    runSh += " \n"
    runSh += "ulimit -s unlimited \n"
    runSh += "set -e \n"
    runSh += " \n"
    runSh += f"python3 doSlurm_NanoAOD.py -i $1 -nF {nFiles} \n"

    with open(f"{slurmDir}/run_nano.sh", "w") as file:
        file.write(runSh)

    os.system(f"chmod +x {slurmDir}/run_nano.sh")

def main():
    parser = defaultParser()
    args = parser.parse_args()

    doSubmit = args.doSubmit
    index = args.index
    nFiles = args.nFiles

    print("Run WWJTo2L2Nu production maker on Slurm")
    print("Submit   -> " + str(doSubmit))

    if doSubmit==1:
        build_condor_submit(nFiles=nFiles)
    elif index>=0:
        runLHEPRoduction(index=index,nFiles=nFiles)
    else:
        print("Bad configuration!!!!")
       # print(files)


if __name__ == '__main__':
    main()
    print("DONE!")
        
