"""
Produce 5 PNG plots from the M5 metrics CSV.
All text is plain ASCII for Windows cp1252 compatibility.
"""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _save(fig, path: str) -> None:
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  Plot saved -> {path}")


def plot_latency_vs_n(df: pd.DataFrame, out: str) -> None:
    sub = df[df["scenario"].isin(["A", "B", "C"])].copy()
    grp = sub.groupby("n_nodes")["consensus_latency_ms"].mean().reset_index()
    fig, ax = plt.subplots()
    ax.plot(grp["n_nodes"], grp["consensus_latency_ms"], marker="o")
    ax.axhline(5000, color="red", linestyle="--", label="5000 ms target")
    ax.set_xlabel("Number of nodes")
    ax.set_ylabel("Consensus latency (ms)")
    ax.set_title("Consensus latency vs node count")
    ax.legend()
    _save(fig, out)


def plot_delivery_vs_failures(df: pd.DataFrame, out: str) -> None:
    sub = df[df["scenario"] == "C"].copy()
    grp = sub.groupby("n_failures")["block_delivery_rate"].mean().reset_index()
    fig, ax = plt.subplots()
    ax.bar(grp["n_failures"].astype(str), grp["block_delivery_rate"])
    ax.axhline(0.90, color="red", linestyle="--", label="90% target")
    ax.set_xlabel("Simultaneous node failures")
    ax.set_ylabel("Block delivery rate")
    ax.set_title("Block delivery rate vs simultaneous failures (N=50)")
    ax.set_ylim(0, 1.05)
    ax.legend()
    _save(fig, out)


def plot_byz_rejection(df: pd.DataFrame, out: str) -> None:
    sub = df[df["scenario"].isin(["A", "B"])].copy()
    grp = sub.groupby("n_nodes")["byzantine_rejection_rate"].mean().reset_index()
    fig, ax = plt.subplots()
    ax.bar(grp["n_nodes"].astype(str), grp["byzantine_rejection_rate"])
    ax.axhline(1.0, color="red", linestyle="--", label="100% target")
    ax.set_xlabel("Number of nodes")
    ax.set_ylabel("Byzantine rejection rate")
    ax.set_title("Byzantine rejection rate (A: N=10 1-Byz, B: N=20 3-Byz)")
    ax.set_ylim(0, 1.05)
    ax.legend()
    _save(fig, out)


def plot_fl_convergence(df: pd.DataFrame, out: str) -> None:
    sub = df[df["scenario"] == "E"].copy()
    if sub.empty:
        return
    fig, ax = plt.subplots()
    for label, grp in sub.groupby("global_comms"):
        tag = "Hierarchical" if label < sub["n_nodes"].iloc[0] else "Flat"
        ax.plot(range(1, len(grp) + 1), grp["fl_weight_delta"].values,
                marker="o", label=f"{tag} (comm={label})")
    ax.set_xlabel("FL round")
    ax.set_ylabel("Weight convergence delta (L2)")
    ax.set_title("FL convergence: flat vs hierarchical FedAvg (N=20)")
    ax.legend()
    _save(fig, out)


def plot_lora_pdr(out: str) -> None:
    from src.network.lora_sim import pdr_deterministic
    distances = [1, 10, 50, 100, 200, 300, 500, 750, 1000]
    pdrs      = [pdr_deterministic(d) * 100 for d in distances]
    fig, ax = plt.subplots()
    ax.plot(distances, pdrs, marker="s")
    ax.set_xlabel("Distance (m)")
    ax.set_ylabel("PDR (%)")
    ax.set_title("LoRa PHY model: PDR vs distance (SF10, BW125, Ptx=14 dBm)")
    ax.set_xscale("log")
    ax.grid(True, which="both", alpha=0.3)
    _save(fig, out)


def generate_all(csv_path: str, results_dir: str) -> None:
    df = pd.read_csv(csv_path)
    plot_latency_vs_n(df,        f"{results_dir}/latency_vs_n.png")
    plot_delivery_vs_failures(df, f"{results_dir}/delivery_vs_failures.png")
    plot_byz_rejection(df,       f"{results_dir}/byz_rejection_rate.png")
    plot_fl_convergence(df,      f"{results_dir}/fl_convergence.png")
    plot_lora_pdr(               f"{results_dir}/lora_pdr_model.png")
