#!/usr/bin/env python3
"""Script for network performance measurement and tuning with iperf3."""

import argparse
import datetime
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

from matplotlib import pyplot as plt
import pandas as pd


def get_iperf_executable(custom_path: str) -> str:
    """Определяет корректный путь к исполняемому файлу iperf3."""
    if custom_path != "iperf":
        exe_path = Path(custom_path).resolve()
        if platform.system() == "Windows" and exe_path.suffix.lower() != ".exe":
            exe_path = exe_path.with_suffix(".exe")
        return str(exe_path)

    cmd = "iperf3" + (".exe" if platform.system() == "Windows" else "")
    resolved = shutil.which(cmd)
    return resolved if resolved else cmd


def build_iperf_cmd(
    iperf_bin: str,
    host: str,
    blks: int,
    test_time: int,
    streams: int,
    reverse: bool,
    protocol: str,
    udp_bandwidth: str = "100G",
) -> List[str]:
    """Формирует список аргументов команды iperf3."""
    cmd = [iperf_bin, "-c", host, "-J", "-t", str(test_time)]

    if protocol == "tcp":
        cmd.extend(["-M", str(blks)])
    else:
        cmd.extend(["-u", "-b", udp_bandwidth, "-l", str(blks)])

    if streams > 1:
        cmd.extend(["-P", str(streams)])
    if reverse:
        cmd.append("-R")
    else:
        cmd.append("--get-server-output")

    return cmd


def run_iperf_test(cmd: List[str], protocol: str, reverse: bool, test_time: int) -> Optional[Dict[str, Any]]:
    """Выполняет запуск iperf3 и возвращает распарсенные метрики."""
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=test_time + 15,
        )
    except subprocess.TimeoutExpired:
        print("  [Error] iperf3 process timed out.")
        return None

    if not proc.stdout.strip():
        print(f"  [Error] iperf3 returned empty output. STDERR: {proc.stderr.strip()}")
        return None

    try:
        raw_json = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        print(f"  [Error] Failed to parse JSON: {e}")
        return None

    if "error" in raw_json:
        print(f"  [Error] iperf3 error: {raw_json['error']}")
        return None

    # Определяем узел с данными (для UDP без реверса метрики получателя находятся в server_output_json)
    root = raw_json
    if protocol == "udp" and not reverse:
        root = raw_json.get("server_output_json", raw_json)

    metrics: Dict[str, Any] = {}

    try:
        if protocol == "tcp":
            end_data = root.get("end", {})
            sum_received = end_data.get("sum_received") or end_data.get("sum_sent", {})
            mbps = round(float(sum_received.get("bits_per_second", 0)) / 1_000_000, 2)

            metrics = {
                "mbps": mbps,
                "lost_percent": 0.0,
                "jitter_ms": 0.0,
                "tr_packets": 0,
            }
            print(f"  Speed: {mbps} Mbps")

        elif protocol == "udp":
            end_sum = root.get("end", {}).get("sum", {})
            mbps = round(float(end_sum.get("bits_per_second", 0)) / 1_000_000, 2)
            lost_pct = round(float(end_sum.get("lost_percent", 0)), 2)
            jitter_ms = round(float(end_sum.get("jitter_ms", 0)), 3)

            lost_packets = int(end_sum.get("lost_packets", 0))
            packets = int(end_sum.get("packets", 0))
            tr_packets = round((packets - lost_packets) / max(test_time, 1))

            metrics = {
                "mbps": mbps,
                "lost_percent": lost_pct,
                "jitter_ms": jitter_ms,
                "tr_packets": tr_packets,
            }
            print(f"  Speed: {mbps} Mbps | Loss: {lost_pct}% | Jitter: {jitter_ms} ms | PPS: {tr_packets}")

    except KeyError as e:
        print(f"  [Error] Missing expected JSON field: {e}")
        return None

    return metrics


def build_graph(png_path: Path, df_summary: pd.DataFrame, df_raw: pd.DataFrame, title: str) -> None:
    """Генерирует и сохраняет график результатов."""
    plt.figure(figsize=(10, 6))

    for direction, color, marker in [("Download", "tab:blue", "o"), ("Upload", "tab:orange", "s")]:
        sub_raw = df_raw[df_raw["direction"] == direction]
        sub_sum = df_summary[df_summary["direction"] == direction]

        if not sub_raw.empty:
            plt.scatter(sub_raw["packet_size"], sub_raw["mbps"], color=color, alpha=0.3, label=f"{direction} (runs)")
        if not sub_sum.empty:
            plt.plot(sub_sum["packet_size"], sub_sum["mbps"], color=color, marker=marker, linestyle="-", label=f"{direction} (avg)")

    plt.xlabel("Packet size (bytes)")
    plt.ylabel("Throughput (Mbps)")
    plt.title(title)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.savefig(png_path, dpi=300)
    plt.close()


def parse_args(args: List[str]) -> argparse.Namespace:
    """Валидация и парсинг параметров командной строки."""
    parser = argparse.ArgumentParser(description="Network performance measurement via iperf3.")
    parser.add_argument("--target", default="127.0.0.1", help="Target host / IP")
    parser.add_argument("-s", "--streams", default=1, type=int, help="Parallel streams")
    parser.add_argument("-o", "--output", required=True, help="Base output file name")
    parser.add_argument("--test-time", default=5, type=int, help="Duration in seconds per test")
    parser.add_argument("--interval", default=100, type=int, help="Step size for packet size range")
    parser.add_argument("--range-from", default=100, type=int, help="Min packet size")
    parser.add_argument("--range-to", default=1500, type=int, help="Max packet size")
    parser.add_argument("--repeat", default=1, type=int, help="Number of repetitions per test")
    parser.add_argument("-p", "--protocol", default="tcp", choices=["tcp", "udp"], help="Transport protocol")
    parser.add_argument("--iperf-file", default="iperf", help="Path or alias for iperf3 binary")
    parser.add_argument("--list-mss", nargs="+", type=int, help="Explicit list of packet sizes (e.g., 650 800 1400)")

    options = parser.parse_args(args)
    if options.range_from > options.range_to:
        parser.error(f"Invalid range: from ({options.range_from}) > to ({options.range_to})")
    if options.test_time <= 0 or options.repeat <= 0 or options.streams <= 0:
        parser.error("Numeric parameters (streams, test-time, repeat) must be > 0")

    return options


def main() -> None:
    options = parse_args(sys.argv[1:])
    iperf_bin = get_iperf_executable(options.iperf_file)

    output_dir = Path("results")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    base_name = output_dir / f"{options.output}_{timestamp}"

    txt_file = base_name.with_suffix(".txt")
    csv_file = base_name.with_suffix(".csv")
    png_file = base_name.with_suffix(".png")

    if options.list_mss:
        packet_sizes = sorted(options.list_mss)
    else:
        packet_sizes = list(range(options.range_from, options.range_to + 1, options.interval))

    records = []

    with open(txt_file, "w", encoding="utf-8") as log:
        log.write(f"Test against {options.target} started at {timestamp}\n")
        log.write(f"Protocol: {options.protocol.upper()} | Streams: {options.streams}\n\n")

        for reverse_mode in [True, False]:
            direction = "Download" if reverse_mode else "Upload"
            print(f"\n{'='*20} Starting {direction} tests {'='*20}")

            for psize in packet_sizes:
                print(f"\n[Testing] Direction: {direction} | Packet Size: {psize}")
                cmd = build_iperf_cmd(
                    iperf_bin,
                    options.target,
                    psize,
                    options.test_time,
                    options.streams,
                    reverse_mode,
                    options.protocol,
                )

                log.write(f"Command: {' '.join(cmd)}\n")

                for rep in range(1, options.repeat + 1):
                    if options.repeat > 1:
                        print(f" Run #{rep}/{options.repeat}:", end="")

                    result = run_iperf_test(cmd, options.protocol, reverse_mode, options.test_time)
                    if result is not None:
                        records.append({
                            "direction": direction,
                            "packet_size": psize,
                            "repeat": rep,
                            "mbps": result["mbps"],
                            "lost_percent": result["lost_percent"],
                            "jitter_ms": result["jitter_ms"],
                            "packets_per_sec": result["tr_packets"],
                        })
                        log.write(f"{psize} {result['mbps']} Mbps\n")

    if not records:
        print("\n[!] No test data collected. Please verify your connection and iperf server.")
        return

    df_raw = pd.DataFrame(records)

    # Агрегация средних значений
    df_summary = (
        df_raw.groupby(["direction", "packet_size"])[
            ["mbps", "lost_percent", "jitter_ms", "packets_per_sec"]
        ]
        .mean()
        .round(2)
        .reset_index()
    )

    # Сохранение структурированных результатов
    df_raw.to_csv(csv_file, index=False)
    print(f"\nData saved to {csv_file}")

    # Построение графиков
    build_graph(png_file, df_summary, df_raw, f"Bandwidth vs Packet Size ({options.protocol.upper()})")
    print(f"Graph saved to {png_file}")
    print(f"Log saved to {txt_file}")


if __name__ == "__main__":
    main()
