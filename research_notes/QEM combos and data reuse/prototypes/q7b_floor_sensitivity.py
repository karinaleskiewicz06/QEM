"""Q7b: sensitivity of the twirl-vs-off log-error contrast (H1-style) to the error floor in log(max(err, floor)),
and arithmetic / RMS alternatives. Reads runs/odra_campaign/w01A/cdr.csv (OLS, near_target)."""
import sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import *  # noqa
import pandas as pd
df = pd.read_csv(REPO / "runs/odra_campaign/w01A/cdr.csv")
df = df[(df.fit == "ols") & (df.train_set == "near_target")]
lines = []
for rung in ("star", "circular"):
    p = df[df.rung == rung].pivot_table(index="eval_index", columns="arm", values="err")
    off, tw = p["off_copies"].values, p["twirl_native"].values
    s = [f"{rung}: geo ratio twirl/off by floor:"]
    for f in (1e-4, 1e-3, 3e-3, 5e-3, 1e-2):
        lr = np.log(np.maximum(tw, f)) - np.log(np.maximum(off, f))
        m, lo, hi = boot_mean_ci(lr)
        s.append(f"floor {f:g}: x{np.exp(m):.2f} [{np.exp(lo):.2f},{np.exp(hi):.2f}]")
    lines.append("  ".join(s))
    lines.append(f"   arithmetic ratio {tw.mean()/off.mean():.2f}; RMS ratio {np.sqrt((tw**2).mean()/(off**2).mean()):.2f}; "
                 "paired abs diff: " + paired_report(tw, off, "twirl", "off"))
txt = "\n".join(lines); (OUT / "q7b_floor_sensitivity.txt").write_text(txt); print(txt)
