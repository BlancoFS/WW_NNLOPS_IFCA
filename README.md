# WW_NNLOPS_IFCA

Instructions to run the prodiction of WWTo2L2Nu POWHEG+MiNNLO NNLOPS sample in the IFCA T3 environment

** CMS Summer24 campaign settings on **

## LHE,GEN,SIM

The first step is the event generation through the gridpack stored in CVMFS:
- `/cvmfs/cms-griddata.cern.ch/phys_generator/gridpacks_tarball/pp/13p6TeV/powheg/WW_MINNLO/WWJTo2L2Nu_powhegMiNNLOPS_6800GeV_slc7_amd64_gcc10_CMSSW_12_6_5_tarball.tgz`

**Need to open the doSlurm.py file and replace the username logic with your IFCA and LXPLUS usernames, and replace the prefix variable with your desired output directory**

```bash
source /cvmfs/cms.cern.ch/cmsset_default.sh
cmsrel CMSSW_14_0_23
cd CMSSW_14_0_23/src
git clone https://github.com/BlancoFS/WW_NNLOPS_IFCA.git
cp WW_NNLOPS_IFCA/* ./
python3 doSlurm.py -s 1
sbatch submit.jdl
```

## DIGI,PREMIX,RECO,AOD

The digitization, pile-up premixing, and reconstruction is performed in a second step, once the GEN-SIM output is completed. To access the pile-up libraries: 

```bash
voms-proxy-init3 --voms cms --rfc --valid 168:00
cp /tmp/x509up_uXXXXXXX $HOME/.proxy
```

Now, **replace your needed username and prefix in doSlurm_AOD.py** and perform:

```bash
find /gpfs/projects/cms/USERNAME/WWTo2L2Nu_Powheg_MiNNLO_13p6TeV/2024/Summer24_X/ -type f -size +10000 > step0_filelist.txt
python3 doSlurm_AOD.py -s 1
sbatch submit.jdl
```

Remember that `/gpfs/projects/cms/USERNAME/WWTo2L2Nu_Powheg_MiNNLO_13p6TeV/2024/Summer24_X/` should be whatever path you used to store your GEN-SIM files.

## MINIAOD,NANOAOD

The MiniAODv6 and NanoAODv15 steps are the fastest ones. Repeat the same operation with the **username and prefix** for `doSlurm_NanoAOD.py` and perform:

```bash
find /gpfs/projects/cms/USERNAME/WWTo2L2Nu_Powheg_MiNNLO_13p6TeV/2024/Summer24-AOD_0/ -type f > step1_filelist.txt
python3 doSlurm_NanoAOD.py -s 1 -nF 50
sbatch submit_nano.jdl
```

The parameter `nF` indicate the number of AOD files that are combined to create a single NanoAODv15 file. By default, I would use 50 to generate NanoAODv15 files with at least 50000 events. If you want to test the output, please use `doNanoValidation.py` or `testGenerator.py`, for early stages.