from DataFormats.FWLite import Events, Handle
import sys

# Label of the gen-particle collection depends on the data tier
GEN_LABEL = {
    "GEN-SIM": "genParticles",
    "AOD":     "genParticles",
    "MINIAOD": "prunedGenParticles",
}

def fingerprint(fname, label, n_events=5):
    """Return a list of (nGen, lead lepton pT, eta) for the first n_events."""
    handle = Handle("std::vector<reco::GenParticle>")
    out = []
    for iev, ev in enumerate(Events(fname)):
        if iev >= n_events:
            break
        ev.getByLabel(label, handle)
        parts = handle.product()
        leptons = [p for p in parts
                   if abs(p.pdgId()) in (11, 13) and p.status() == 1]
        lead = max(leptons, key=lambda p: p.pt(), default=None)
        out.append((
            parts.size(),
            round(lead.pt(), 4)  if lead else None,
            round(lead.eta(), 4) if lead else None,
        ))
    return out

files = [
    #"/gpfs/projects/cms/sblancof/WWTo2L2Nu_Powheg_MiNNLO_13p6TeV/2024/Summer24_0/GEN-SIM/HIG-RunIII2024Summer24wmLHEGS-00770_3.root",
    #"/gpfs/projects/cms/sblancof/WWTo2L2Nu_Powheg_MiNNLO_13p6TeV/2024/Summer24_0/GEN-SIM/HIG-RunIII2024Summer24wmLHEGS-00770_4.root",
    "/gpfs/projects/cms/casertam/WWTo2L2Nu_Powheg_MiNNLO_13p6TeV/2024/Summer24_0/HIG-RunIII2024Summer24wmLHEGS-00770_0.root",
    "/gpfs/projects/cms/casertam/WWTo2L2Nu_Powheg_MiNNLO_13p6TeV/2024/Summer24_0/HIG-RunIII2024Summer24wmLHEGS-00770_1.root",
]
label = GEN_LABEL["AOD"]

prints = {f: fingerprint(f, label) for f in files}
for f, fp in prints.items():
    print(f.split("/")[-1])
    for i, (n, pt, eta) in enumerate(fp):
        print(f"   event {i}: nGen={n:5d}  lead lepton pT={pt}  eta={eta}")

ref = prints[files[0]]
for f in files[1:]:
    same = sum(a == b for a, b in zip(ref, prints[f]))
    verdict = "IDENTICAL -> same seeds" if same == len(ref) else "different -> OK"
    print(f"{files[0].split('/')[-1]} vs {f.split('/')[-1]}: "
          f"{same}/{len(ref)} events match ({verdict})")
