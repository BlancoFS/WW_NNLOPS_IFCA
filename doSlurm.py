import ROOT

import os
import sys
from sys import exit
from sys import argv
import argparse
import time
import json
from pathlib import Path
import subprocess
import requests

ROOT.gROOT.SetBatch(True)
ROOT.TH1.SetDefaultSumw2(True)

username = os.environ["USER"]
if username == "blancose":
    username = "sblancof"  ### Use CERN username for Sergio Blanco

run = "HIG-RunIII2024Summer24wmLHEGS-00770_1_cfg.py"
campaign = "Summer24_0"

fileOut1 = "HIG-RunIII2024Summer24wmLHEGS-00770.root"
fileOut2 = "HIG-RunIII2024Summer24wmLHEGS-00770_inLHE.root"

prefix = f"/gpfs/projects/cms/sblancof/WWTo2L2Nu_Powheg_MiNNLO_13p6TeV/2024/{campaign}/GEN-SIM"
redirector = ""

def defaultParser():
    parser = argparse.ArgumentParser(add_help=False)

    def list_of_strings(arg):
        return arg.split(',')

    parser.add_argument(
        "-n",
        "--numJobs",
        type=int,
        help="Index",
        required=False,
        default=0,
    )

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

    return parser


def runLHEPRoduction(index=0):

    ## Copy run script to TMPDIR
    tmp_dir = f"{os.environ['TMPDIR']}/job_{index}"
    Path(tmp_dir).mkdir(parents=True, exist_ok=True)
    
    procString = f"cp {run} {tmp_dir}"    
    proc = subprocess.Popen(procString,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    out, err = proc.communicate()
    
    Path(prefix).mkdir(parents=True, exist_ok=True)
    os.chdir(tmp_dir)

    #### Establish the campaign and index numbers for seeding
    campaign_number = int(campaign.split("_")[1])

    old = "RPLME_CAMPAIGN"
    new = str(campaign_number)
    proc = subprocess.run(
        ["sed", "-i", f"s|{old}|{new}|g", run],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stderr)

    old = "RPLME_INDEX"
    new = str(index)
    proc = subprocess.run(
        ["sed", "-i", f"s|{old}|{new}|g", run],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stderr)

        
    job_id = 500 * campaign_number + index
    print(f"Using seed: {1000 * (job_id + 1)}+i")

    ### ----------
    
    print("Running cmsRun...")
    procString = f"cmsRun {run}"
    proc = subprocess.Popen(
        procString,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, err = proc.communicate()
        
    tmpFile1 = fileOut1.split(".root")[0] + f"_{index}.root"
    tmpFile2 = fileOut2.split(".root")[0] + f"_{index}.root"
    
    proc = subprocess.Popen(f"mv {fileOut1} {prefix}/{tmpFile1}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    
    proc = subprocess.Popen(f"mv {fileOut2} {prefix}/{tmpFile2}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
            
def build_condor_submit(numJobs=-1):

    if numJobs != 500:
        print("Wrong number of jobs!!!! Going with 500 as deafult")
        numJobs = 500

    slurmDir = os.path.abspath(os.getcwd())
    fSh = ""
    fSh += "#!/bin/sh \n"
    fSh += f"#SBATCH --job-name=WWTo2L2Nu_{campaign} \n"
    #fSh += "#SBATCH --partition=acompute_cms \n"
    fSh += "#SBATCH --account=cms \n"
    fSh += "#SBATCH --cpus-per-task=1 \n"
    fSh += "#SBATCH --mem-per-cpu=8G \n"
    fSh += "#SBATCH --time=48:00:00   # equivalent to workday (adjust to your cluster) \n"
    fSh += f"#SBATCH --array=0-{numJobs} \n"
    fSh += "\n"
    #fSh += "export APPTAINER_BINDPATH=/afs,/cvmfs,/cvmfs/grid.cern.ch/etc/grid-security:/etc/grid-security,/cvmfs/grid.cern.ch/etc/grid-security/vomses:/etc/vomses,/gpfs,/etc/pki/ca-trust,/run/user,/tmp,/var/run/user,/etc/sysconfig,/etc:/orig/etc \n"
    #fSh += f"apptainer -s exec /cvmfs/unpacked.cern.ch/gitlab-registry.cern.ch/cms-cat/cmssw-lxplus/cmssw-el7-lxplus:latest/ {os.path.dirname(os.path.abspath(__file__))}/run.sh $SLURM_ARRAY_TASK_ID \n"
    fSh += f"{os.path.dirname(os.path.abspath(__file__))}/run.sh $SLURM_ARRAY_TASK_ID \n"
    
    with open(f"{slurmDir}/submit.jdl", "w") as file:
        file.write(fSh)

    runSh = "#!/bin/bash \n"
    runSh += " \n"
    runSh += f"cd {os.path.dirname(os.path.abspath(__file__))} \n"
    runSh += "source /cvmfs/cms.cern.ch/cmsset_default.sh \n"
    runSh += "cmsenv \n"
    runSh += " \n"
    runSh += "echo $1 \n"
    runSh += " \n"
    runSh += "ulimit -s unlimited \n"
    runSh += "set -e \n"
    runSh += " \n"
    runSh += "python3 doSlurm.py -i $1 \n"

    with open(f"{slurmDir}/run.sh", "w") as file:
        file.write(runSh)

    os.system(f"chmod +x {slurmDir}/run.sh")

def main():
    parser = defaultParser()
    args = parser.parse_args()

    doSubmit = args.doSubmit
    numJobs = args.numJobs
    index = args.index

    print("Run efficiency maker")
    print("Submit   -> " + str(doSubmit))
    print("N. jobs  -> ", str(numJobs))

    if doSubmit==1:
        build_condor_submit(numJobs=numJobs)
    elif index>=0:
        runLHEPRoduction(index=index)
    else:
        print("Bad configuration!!!!")
       # print(files)


if __name__ == '__main__':
    main()
    print("DONE!")
        
