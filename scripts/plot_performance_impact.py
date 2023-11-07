#!/usr/bin/env python3.11

import argparse as ap
import json
import math
import os
import re
from collections import defaultdict

import latex
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import rc
from matplotlib.ticker import FixedLocator, FuncFormatter, MaxNLocator
from palettable.cartocolors.qualitative import Safe_6


def parse_args():
    parser = ap.ArgumentParser()
    parser.add_argument("commit", type=str)
    return parser.parse_args()


def format_number(n):
    if n < 1:
        return str(n)
    return str(int(n))

    for x in [1, 3, 5, 10]:
        if n == x:
            return str(int(n))
    return ""


def to_s(lst):
    return [x / 10**9 for x in lst]


def get_old_new_latencies(old_path, new_path):
    with open(old_path) as old_file:
        old_data = json.load(old_file)

    with open(new_path) as new_file:
        new_data = json.load(new_file)

    if old_data["context"]["benchmark_mode"] != new_data["context"]["benchmark_mode"]:
        exit("Benchmark runs with different modes (ordered/shuffled) are not comparable")

    old_latencies = list()
    new_latencies = list()

    for old, new in zip(old_data["benchmarks"], new_data["benchmarks"]):
        name = old["name"]
        # Create numpy arrays for old/new successful/unsuccessful runs from benchmark dictionary
        old_successful_durations = np.array([run["duration"] for run in old["successful_runs"]], dtype=np.float64)
        new_successful_durations = np.array([run["duration"] for run in new["successful_runs"]], dtype=np.float64)
        old_unsuccessful_durations = np.array([run["duration"] for run in old["unsuccessful_runs"]], dtype=np.float64)
        new_unsuccessful_durations = np.array([run["duration"] for run in new["unsuccessful_runs"]], dtype=np.float64)
        # np.mean() defaults to np.float64 for int input
        old_latencies.append(np.mean(old_successful_durations))
        new_latencies.append(np.mean(new_successful_durations))

    return old_latencies, new_latencies


def get_trend(old, new):
    diff = new / old
    if diff <= 0.95:
        return "better"
    elif diff >= 1.05:
        return "worse"
    return "same"


def main(commit):
    sns.set()
    sns.set_theme(style="whitegrid")

    mpl.use("pgf")

    plt.rcParams.update(
        {
            "font.family": "serif",  # use serif/main font for text elements
            "text.usetex": True,  # use inline math for ticks
            "pgf.rcfonts": False,  # don't setup fonts from rc parameters
            "pgf.preamble": r"""\usepackage{iftex}
  \ifxetex
    \usepackage[libertine]{newtxmath}
    \usepackage[tt=false]{libertine}
    \setmonofont[StylisticSet=3]{inconsolata}
  \else
    \ifluatex
      \usepackage[libertine]{newtxmath}
      \usepackage[tt=false]{libertine}
      \setmonofont[StylisticSet=3]{inconsolata}
    \else
       \usepackage[tt=false, type1=true]{libertine}
       \usepackage[varqu]{zi4}
       \usepackage[libertine]{newtxmath}
    \fi
  \fi""",
        }
    )

    benchmarks = ["TPCH", "TPCDS", "JoinOrder", "StarSchema"]
    base_palette = Safe_6.hex_colors

    for benchmark in benchmarks:
        common_path = f"hyriseBenchmark{benchmark}_{commit}_st"
        if benchmark != "JoinOrder":
            common_path = common_path + "_s10"
        old_path = common_path + "_all_off.json"
        new_path = common_path + "_plugin.json"

        old_latencies, new_latencies = get_old_new_latencies(old_path, new_path)
        trend = [get_trend(old, new) for old, new in zip(old_latencies, new_latencies)]
        values = pd.DataFrame(data={"old": to_s(old_latencies), "new": to_s(new_latencies), "trend": trend})
        colors = {"worse": base_palette[1], "same": "grey", "better": base_palette[3]}

        sns.scatterplot(data=values, x="old", y="new", palette=colors, hue="trend", s=80, legend=False)

        ax = plt.gca()
        plt.ylabel("Latency w/ optimizations [s]", fontsize=8 * 2)
        plt.xlabel("Base latency [s]", fontsize=8 * 2)
        ax.tick_params(axis="both", which="major", labelsize=7 * 2)
        ax.tick_params(axis="both", which="minor", labelsize=7 * 2)

        ax.set_yscale("log")
        ax.set_xscale("log")

        print(
            benchmark,
            round((1 - sum(new_latencies) / sum(old_latencies)) * 100),
            "% improvement,",
            len(values[values.trend == "better"]),
            "better,",
            len(values[values.trend == "worse"]),
            "worse",
        )

        min_lim = min(ax.get_ylim()[0], ax.get_xlim()[0])
        max_lim = max(ax.get_ylim()[1], ax.get_xlim()[1])

        possible_ticks_below_one = [10 ** (-exp) for exp in reversed(range(1, 4))]
        possible_ticks_above_one = [1, 3, 5, 10]
        ticks = list()
        for tick in possible_ticks_below_one:
            if tick >= min_lim:
                ticks.append(tick)
        for tick in possible_ticks_above_one:
            if tick <= max_lim:
                ticks.append(tick)
        ax.set_ylim(min_lim, max_lim)
        ax.set_xlim(min_lim, max_lim)

        sns.lineplot(x=[min_lim, max_lim], y=[min_lim, max_lim], color="lightgrey", sizes=(0.2, 0.2), legend=False)

        ax.xaxis.set_major_locator(FixedLocator(ticks))
        ax.yaxis.set_major_locator(FixedLocator(ticks))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: format_number(x)))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: format_number(x)))
        plt.grid(dashes=(3, 5))

        fig = plt.gcf()
        column_width = 3.3374
        fig_width = column_width * 0.475 * 2
        fig.set_size_inches(fig_width, fig_width)
        plt.tight_layout(pad=0)

        plt.savefig(f"{benchmark}_log.pdf", dpi=300, bbox_inches="tight")
        plt.close()


if __name__ == "__main__":
    main(parse_args().commit)
