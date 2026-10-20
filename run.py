#!/usr/bin/env python3
"""Script for network performance measurement and tuning with iperf3."""
import argparse
import datetime
import json
import os
import platform
import re
import subprocess
import sys
import time
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

def getcmd(host, blks, test_time, stream_count, reverse, protocol, iperffile):
    """Get iperf3 command line string."""
    cmd = os.path.realpath(iperffile) if iperffile != "iperf" else "iperf3"
    if platform.system() == "Windows":
        cmd += ".exe"
        
    cmd += f" -c {host} -J -t {test_time}"
    cmd += f" -M {blks}" if protocol == "tcp" else f" -u -b 100G -l {blks}"
    
    if not reverse:
        cmd += " --get-server-output"
    if stream_count > 1:
        cmd += f" -P {stream_count}"
    if reverse:
        cmd += " -R"
    return cmd

def run_iperf_test(filename, data, blks, cmd, reverse, protocol, test_time):
    """Run iperf test and parse common JSON output for TCP/UDP."""
    print(f"Packet Size: {blks}")
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, _ = proc.communicate()
    
    try:
        storedata = json.loads(out.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"Error parsing iperf output for size {blks}: {e}")
        return

    # Определяем корневой узел данных в зависимости от направления и протокола
    is_udp_server = (protocol == "udp" and not reverse)
    root = storedata["server_output_json"] if is_udp_server else storedata

    if protocol == "tcp":
        res = round(float(root["end"]["sum_received"]["bits_per_second"]) / 1000000)
        print(f"{'Download' if reverse else 'Upload'} Mbps: {res}")
        
        mode = "r" if reverse else "t"
        data[f"list{mode}x"].append(blks)
        data[f"list{mode}y"].append(res)
    
    elif protocol == "udp":
        timerenge = np.arange(0, test_time, 1)
        list_res = [
            round(float(root["intervals"][t]["sum"]["bits_per_second"]) / 1000000)
            for t in timerenge if t < len(root["intervals"])
        ]
        res = round(sum(list_res) / test_time) if list_res else 0
        
        end_sum = root["end"]["sum"]
        procentlost = round(float(end_sum["lost_percent"])) if reverse else round(float(end_sum["bits_per_second"]))
        jitter_ms = float(end_sum["jitter_ms"])
        lost_packets = round(float(end_sum["lost_packets"]))
        sent_packets = round(float(end_sum["packets"]))
        tr_packets = round((sent_packets - lost_packets) / test_time)

        print(f"{'Download' if reverse else 'Upload'} Mbps: {res} | Lost: {procentlost}% | Jitter: {jitter_ms}ms")
        
        mode = "r" if reverse else "t"
        data[f"list{mode}x"].append(blks)
        data[f"list{mode}y"].append(res)
        data[f"listprocent{mode}"].append(procentlost)
        data[f"listjitter_ms_{mode}"].append(jitter_ms)
        data[f"tr_packets_{mode}"].append(tr_packets)

    add_line(filename, blks, res)

def get_curtime():
    """Get current time string."""
    return datetime.datetime.now().strftime("--%Y-%m-%d--%H.%M.%S")

def add_line(filename, value1, value2):
    """Append line to a file safely using context manager."""
    with open(filename, "a", encoding="utf-8") as out_file:
        out_file.write(f"{value1} {value2}\n")

def clean_txt_file(filename):
    """Clear file content safely."""
    with open(filename, "w", encoding="utf-8") as out_file:
        out_file.truncate()

def graph(png_filename, x_1, y_1, x_2, y_2, ax_1, ay_1, ax_2, ay_2, title, max_y):
    """Create graph based on test results."""
    plt.figure()
    if max_y < 1000:
        plt.ylim(1, 1000)

    plt.scatter(x_1, y_1)
    plt.scatter(x_2, y_2)
    plt.plot(ax_1, ay_1, "o-", label="Download")
    plt.plot(ax_2, ay_2, "o-", label="Upload")
    plt.xlabel("Packet size")
    plt.ylabel("Mbps")
    plt.title(title)
    plt.legend()
    plt.savefig(png_filename)
    plt.close()

def argparse_hostname_or_ip(value):
    """Parse command line host or IP value."""
    allowed = re.compile(r"(?!-)[a-z0-9\.\:\[\]-]{1,253}(?<!-)$", re.IGNORECASE)
    if not allowed.match(value):
        raise argparse.ArgumentTypeError(f"'{value}' is an invalid host name or IP address")
    return str(value)

def argparse_positive_int(value):
    """Parse command line positive numeric value."""
    if not str(value).isdigit() or (int(value) <= 0):
        raise argparse.ArgumentTypeError(f"'{value}' is an invalid positive numeric value")
    return int(value)

def add_to_csv(prot, x_1, y_1, y_2, lost_r, lost_t, jitter_ms_r, jitter_ms_t, tr_packets_r, tr_packets_t, scv_filename):
    """Add results to CSV file."""
    datacsv = pd.DataFrame({
        "Packet size": x_1,
        "Download": y_1,
        "Upload": y_2
    })
    if prot == "udp":
        datacsv["R Lost in procent"] = lost_r
        datacsv["T Lost in procent"] = lost_t
        datacsv["R Jitter"] = jitter_ms_r
        datacsv["T Jitter"] = jitter_ms_t
        datacsv["Packets received on Client"] = tr_packets_r
        datacsv["Packets received on Backend"] = tr_packets_t
    datacsv.to_csv(scv_filename, index=False)

def get_options(args):
    """Parse command line options."""
    parser = argparse.ArgumentParser(description="Performance test.")
    parser.add_argument("--target", default="127.0.0.1", type=argparse_hostname_or_ip, help="destination")
    parser.add_argument("-s", "--streams", default=1, type=argparse_positive_int, help="number of parallel test streams")
    parser.add_argument("-o", "--output", required=True, help="output file name")
    parser.add_argument("--test-time", default=5, type=argparse_positive_int, help="test duration in seconds")
    parser.add_argument("--interval", default=100, type=argparse_positive_int, help="MSS interval increment")
    parser.add_argument("--range-from", default=100, type=argparse_positive_int, help="MSS range start")
    parser.add_argument("--range-to", default=1500, type=argparse_positive_int, help="MSS range end")
    parser.add_argument("--repeat", default=1, type=argparse_positive_int, help="Number of repetitions")
    parser.add_argument("-p", "--protocol", default="tcp", choices=["tcp", "udp"], help="Protocol usage")
    parser.add_argument("--iperf-file", default="iperf", help="Set custom name for iperf file")
    parser.add_argument("--list-mss", nargs="+", type=int, help="MSS list. Ex: 650 800 1400")

    options = parser.parse_args(args)
    if options.range_from > options.range_to:
        print(f"invalid range order: [{options.range_from}, {options.range_to}]")
        sys.exit(-1)
    return options

def main():
    """Run main application function."""
    options = get_options(sys.argv[1:])
    folder = "results" + os.path.sep
    os.makedirs(folder, exist_ok=True)

    base_name = f"{folder}{options.output}{get_curtime()}"
    filename = base_name + ".txt"
    scv_filename = base_name + ".csv"
    png_filename = base_name + ".png"

    psize = options.list_mss if options.list_mss is not None else np.arange(options.range_from, options.range_to, options.interval)

    clean_txt_file(filename)
    add_line(filename, "Packet_Size", "Mbps")

    data = {k: [] for k in ["listrx", "listry", "listtx", "listty", "listarx", "listary", "listatx", "listaty",
                           "listprocentr", "listprocentt", "listjitter_ms_r", "listjitter_ms_t", "tr_packets_r", "tr_packets_t"]}

    # Тестирование в обоих направлениях (Download: True, Upload: False)
    for reverse_mode in [True, False]:
        mode_str = "Download" if reverse_mode else "Upload"
        cmd_all = getcmd(options.target, psize, options.test_time, options.streams, reverse_mode, options.protocol, options.iperf_file)
        print(f"\n{mode_str} command: {cmd_all}")
        add_line(filename, f"Command for {mode_str}", cmd_all)
        
        for blks in psize:
            total_y = 0
            cmd = getcmd(options.target, blks, options.test_time, options.streams, reverse_mode, options.protocol, options.iperf_file)
            for _ in range(options.repeat):
                run_iperf_test(filename, data, blks, cmd, reverse_mode, options.protocol, options.test_time)
                y_array = data["listry"] if reverse_mode else data["listty"]
                total_y += y_array[-1] if y_array else 0
                
            suffix = "r" if reverse_mode else "t"
            x_array = data["listrx"] if reverse_mode else data["listtx"]
            data[f"lista{suffix}x"].append(x_array[-1] if x_array else blks)
            data[f"lista{suffix}y"].append(total_y / options.repeat)

    max_y = max(max(data["listry"] or [0]), max(data["listty"] or [0]), max(data["listary"] or [0]), max(data["listaty"] or [0]))

    graph(png_filename, data["listrx"], data["listry"], data["listtx"], data["listty"],
          data["listarx"], data["listary"], data["listatx"], data["listaty"], options.output, max_y)

    add_to_csv(options.protocol, data["listrx"], data["listry"], data["listty"], data["listprocentr"],
               data["listprocentt"], data["listjitter_ms_r"], data["listjitter_ms_t"], data["tr_packets_r"], data["tr_packets_t"], scv_filename)

if __name__ == "__main__":
    main()
