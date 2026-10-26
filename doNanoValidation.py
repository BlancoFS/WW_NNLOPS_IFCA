import ROOT
import uproot
import numpy as np
import subprocess
import matplotlib.pyplot as plt
import awkward as ak

path = "/gpfs/projects/cms/sblancof/WWTo2L2Nu_Powheg_MiNNLO_13p6TeV/2024/Summer24-NanoAODv15_0/*.root"

cmd = "find {} -type f".format(path)
fnames = subprocess.check_output(cmd, shell=True).strip().split(b'\n')
files = [fname.decode('ascii') for fname in fnames]

print(files)

gensumw2 = 0
xs = 12.96
for fname in files:
    df_tmp = uproot.open(fname)
    gensumw2 += df_tmp["Runs"]["genEventSumw"].array()[0]

baseW = xs * 1000 / gensumw2

ROOT.gInterpreter.Declare(
    """
    ROOT::RVecF getGenVars(ROOT::RVecF LHEPart_pt, ROOT::RVecF LHEPart_eta, ROOT::RVecF LHEPart_phi, ROOT::RVecF LHEPart_mass, ROOT::RVecF LHEPart_pdgId){

        float ptll = -99.9;
        float mll = -99.9;
        float dphill = -99.9;
        float ptww = -99.9;
        float mww = -99.9;        
        
        TLorentzVector WP;
        TLorentzVector WM;

        TLorentzVector LP;
        TLorentzVector LM;
        
        int found = 0;
        int foundLeptonP = 0;
        int foundLeptonM = 0;
        for (int i=0; i<LHEPart_pt.size(); i++){
            if (LHEPart_pdgId[i] == 24){
                WM.SetPtEtaPhiM(LHEPart_pt[i],LHEPart_eta[i],LHEPart_phi[i],LHEPart_mass[i]);
                found++;
            }else if (LHEPart_pdgId[i] == -24){
                WP.SetPtEtaPhiM(LHEPart_pt[i],LHEPart_eta[i],LHEPart_phi[i],LHEPart_mass[i]);
                found++;
            }

            if (LHEPart_pdgId[i]==13 || LHEPart_pdgId[i]==11 || LHEPart_pdgId[i]==15){
                LM.SetPtEtaPhiM(LHEPart_pt[i],LHEPart_eta[i],LHEPart_phi[i],LHEPart_mass[i]);
                foundLeptonM++;
            }else if (LHEPart_pdgId[i]==-13 || LHEPart_pdgId[i]==-11 || LHEPart_pdgId[i]==-15){
                LP.SetPtEtaPhiM(LHEPart_pt[i],LHEPart_eta[i],LHEPart_phi[i],LHEPart_mass[i]);
                foundLeptonP++;
            }
                
        }
        if (found>1){
            mww = (WP+WM).M();
            ptww = (WP+WM).Pt();
        }

        if (foundLeptonM>0 && foundLeptonP>0){
            ptll = (LP+LM).Pt();
            mll = (LP+LM).M();
            dphill = fabs(LM.DeltaPhi(LP));
        }

        ROOT::RVecF result{mww,ptww,ptll,mll,dphill};
        return result;
    }
    """
)

df = ROOT.RDataFrame("Events", files)

##### Create reco leptons --------------------------
ROOT.gInterpreter.Declare(
    """
    ROOT::RVecI sortedIndices(ROOT::RVecF variable){
    // return sortedIndices based on variable
    return Reverse(Argsort(variable));
    }
    """
)
ROOT.gInterpreter.Declare("""
using namespace ROOT;
using namespace ROOT::VecOps;
ROOT::RVecB reduce_cond_any(ROOT::RVecB condition, uint size1, uint size2){
ROOT::RVecB r;
for (uint i = 0; i < size1; i++){
bool c = false;
for (uint j = 0; j < size2; j++){
if (condition[i * size2 + j]){
c = true; break;
}
}
r.push_back(c);
}
return r;
}
""")

df = df.Define("Lepton_pt", "ROOT::VecOps::Concatenate(Electron_pt, Muon_pt)")
df = df.Define("Lepton_sorting", "sortedIndices(Lepton_pt)")
df = df.Redefine("Lepton_pt", "Take(Lepton_pt, Lepton_sorting)")
Lepton_var = ["eta", "phi", "pdgId"]
for prop in Lepton_var:
    df = df.Define(
        f"Lepton_{prop}",
        f"ROOT::VecOps::Concatenate(Electron_{prop}, Muon_{prop})",
    )
    df = df.Redefine(f"Lepton_{prop}", f"Take(Lepton_{prop}, Lepton_sorting)")

df = df.Define(
    "Lepton_electronIdx",
    "ROOT::VecOps::Concatenate((ROOT::RVecI)ROOT::VecOps::Range(nElectron) , ROOT::RVecI(nMuon, -1))",
)
df = df.Redefine(
    "Lepton_electronIdx", "Take(Lepton_electronIdx, Lepton_sorting)"
)
df = df.Define(
    "Lepton_muonIdx",
    "ROOT::VecOps::Concatenate(ROOT::RVecI(nElectron, -1), (ROOT::RVecI)ROOT::VecOps::Range(nMuon))",
)
df = df.Redefine("Lepton_muonIdx", "Take(Lepton_muonIdx, Lepton_sorting)")

df = df.Define("LeptonMask_JC", "(Lepton_pt >= 10)")
df = df.Define("Jet_Lepton_comb", "ROOT::VecOps::Combinations(Jet_pt.size(), Lepton_pt[LeptonMask_JC].size())")

df = df.Define("dR2", """
ROOT::VecOps::DeltaR2(
Take(Jet_eta, Jet_Lepton_comb[0]), 
Take(Lepton_eta, Jet_Lepton_comb[1]), 
Take(Jet_phi, Jet_Lepton_comb[0]), 
Take(Lepton_phi, Jet_Lepton_comb[1])
)""")

df = df.Define("CleanJet_geometrical", "! reduce_cond_any(dR2 < (0.3*0.3), Jet_pt.size(), Lepton_pt[LeptonMask_JC].size())")
df = df.Define("CleanJetMask", f"(Jet_pt >= 15.0 && abs(Jet_eta) <= 4.7 && CleanJet_geometrical)")
df = df.Define("CleanJet_correctedjetIdx", "ROOT::VecOps::Range(nJet)[CleanJetMask]")
for prop in ["pt", "eta", "phi", "mass"]:
    df = df.Define(f"CleanJet_{prop}", f"Jet_{prop}[CleanJetMask]")

df = df.Define("njets", "Sum(CleanJet_pt>30.0)")
    
### Create lhe variables -------------
df = df.Define("GenVars", "getGenVars(LHEPart_pt, LHEPart_eta, LHEPart_phi, LHEPart_mass, LHEPart_pdgId)")
df = df.Define("mww","GenVars[0]")
df = df.Define("ptww","GenVars[1]")
df = df.Define("ptll","GenVars[2]")
df = df.Define("mll","GenVars[3]")
df = df.Define("dphill","GenVars[4]")

df = df.Define("XSWeight", f"{baseW} * genWeight")

histo_mww = df.Histo1D(("h_mww", "h_mww", 200, 0.0, 500.0), "mww", "XSWeight")
histo_ptww = df.Histo1D(("h_ptww", "h_ptww", 200, 0.0, 500.0), "ptww", "XSWeight")
histo_ptll = df.Histo1D(("h_ptll", "h_ptll", 100, 0.0, 200.0), "ptll", "XSWeight")
histo_mll = df.Histo1D(("h_mll", "h_mll", 100, 0.0, 200.0), "mll", "XSWeight")
histo_dphill = df.Histo1D(("h_dphill", "h_dphill", 25, 0.0, 3.1416), "dphill", "XSWeight")
histo_njets = df.Histo1D(("h_njets", "h_njets", 6, 0, 5), "njets", "XSWeight")


outFile = ROOT.TFile("nanoHistograms_minnlo.root", "RECREATE")
outFile.cd()
histo_mww.Clone().Write()
histo_ptww.Clone().Write()
histo_ptll.Clone().Write()
histo_mll.Clone().Write()
histo_dphill.Clone().Write()
histo_njets.Clone().Write()
outFile.Close()
