#!/usr/bin/env python3
"""Script for network performance measurement and tuning with iperf3."""
import sys
import os
import time
import datetime
import json
import subprocess
import platform
import argparse
import re
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt


def getcmd(host, blks, test_time, stream_count, reverse, protocol, iperffile):
    """Get iperf3 command line string."""
    cmd = iperf(iperffile)
    if platform.system() == 'Windows':
        cmd += ".exe"
    if protocol == 'tcp':
        cmd += (
            ' -c ' + host
            + ' -J -M ' + str(blks)
            + ' -t ' + str(test_time)
        )
        if not reverse:
            cmd += ' --get-server-output'
    else:
        cmd += (
            ' -c ' + host + ' -J -t ' + str(test_time) + ' -u -b 100G -l '
            + str(blks)
        )
        if not reverse:
            cmd += ' --get-server-output'
    if stream_count > 1:
        cmd += ' -P ' + str(stream_count)
    if reverse:
        cmd += ' -R'
    return cmd


def runtcp(filename, data, blks, cmd, reverse):
    """Run iperf test with TCP."""
    print('Packet Size', blks)
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    out = proc.stdout.read()
    storedata = json.loads(out)
    res = round(float(
        (storedata['end']['sum_received']['bits_per_second'])/1000000))
    add_line(filename, blks, res)
    proceedresulttcp(reverse, res, blks, data)


def runudp(filename, data, blks, cmd, reverse, test_time):
    """Run iperf test with UDP."""
    print('Packet Size', blks)
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    out = proc.stdout.read()
    storedata = json.loads(out)
    timerenge = np.arange(0, test_time, 1)
    list_res = []
    if reverse:
        for timetest in timerenge:
            res = round(float((storedata['intervals'][timetest]['sum']
                        ['bits_per_second'])/1000000))
            list_res.append(res)
        procentlost = round(float(storedata['end']['sum']['lost_percent']))
        jitter_ms = (float(storedata['end']['sum']['jitter_ms']))
        lost_packets = round(float(storedata['end']['sum']['lost_packets']))
        sent_packets = round(float(storedata['end']['sum']['packets']))
        tr_packets = round((sent_packets - lost_packets)/test_time)
    else:
        for timetest in timerenge:
            res = round(float((storedata['server_output_json']['intervals']
                        [timetest]['sum']['bits_per_second'])/1000000))
            list_res.append(res)
        procentlost = round(float(storedata['server_output_json']['end']
                            ['sum']['bits_per_second']))
        jitter_ms = (float(storedata['server_output_json']['end']
                     ['sum']['jitter_ms']))
        lost_packets = round(float(storedata['server_output_json']['end']
                             ['sum']['lost_packets']))
        sent_packets = round(float(storedata['server_output_json']['end']
                             ['sum']['packets']))
        tr_packets = round((sent_packets - lost_packets)/test_time)
    res = round((sum(list_res))/test_time)
    add_line(filename, blks, res)
    proceedresultudp(
        reverse, res, blks, data, procentlost,
        jitter_ms, tr_packets)


def proceedresulttcp(reverse, res, blks, data):
    """Record tcp results into data."""
    if reverse:
        print('Download Mbps', res)
        data['listrx'].append(blks)
        data['listry'].append(res)
    else:
        print('Upload Mbps', res)
        data['listtx'].append(blks)
        data['listty'].append(res)


def proceedresultudp(
                    reverse, res, blks, data, procentlost,
                    jitter_ms, tr_packets
                    ):
    """Record udp results into data."""
    if reverse:
        print(
            'Download Mbps:', res, 'Packet Lost in procent:',
            procentlost, 'jitter_ms:', jitter_ms,
            'Packets transmitted', tr_packets
            )
        data['listrx'].append(blks)
        data['listry'].append(res)
        data['listprocentr'].append(procentlost)
        data['listjitter_ms_r'].append(jitter_ms)
        data['tr_packets_r'].append(tr_packets)
    else:
        print(
            'Upload Mbps:', res, 'Packet Lost in procent:',
            procentlost, 'jitter_ms:', jitter_ms,
            'Packets transmitted', tr_packets
            )
        data['listtx'].append(blks)
        data['listty'].append(res)
        data['listprocentt'].append(procentlost)
        data['listjitter_ms_t'].append(jitter_ms)
        data['tr_packets_t'].append(tr_packets)


def get_curtime():
    """Get current time string."""
    timestamp = time.time()
    return datetime.datetime.fromtimestamp(
        timestamp).strftime('--%Y-%m-%d--%H.%M.%S')


# Add all result in txt file for additional using in xls table
def add_line(filename, value1, value2):
    """Append line to a file."""
    out_file = open(filename, 'a')
    out_file.write(str(value1) + ' ' + str(value2) + "\n")
    out_file.close()


# Clean txt file and crate title for columns
def clean_txt_file(filename):
    """Clear file content."""
    out_file = open(filename, 'w')
    out_file.truncate()
    out_file.close()


def foldername():
    """Get default output folder name."""
    return 'results' + os.path.sep


def graph(
        png_filename,
        x_1,
        y_1,
        x_2,
        y_2,
        ax_1,
        ay_1,
        ax_2,
        ay_2,
        title,
        max_y):
    """Create graph based on test results."""
    if max_y < 1000:
        plt.ylim(1, 1000)

    plt.scatter(x_1, y_1)
    plt.scatter(x_2, y_2)
    plt.plot(ax_1, ay_1, 'o-', label='Download')
    plt.plot(ax_2, ay_2, 'o-', label='Upload')
    plt.xlabel('Packet size')
    plt.ylabel('Mbps')
    plt.title(title)
    plt.legend()
    plt.savefig(png_filename)


def argparse_hostname_or_ip(value):
    """Parse command line host or IP value."""
    # IPv6, IPv4 or hostname
    allowed = re.compile(
        r"(?!-)[a-z0-9\.\:\[\]-]{1,253}(?<!-)$",
        re.IGNORECASE
    )
    if not allowed.match(value):
        raise argparse.ArgumentTypeError(
            "'%s' is an invalid host name or IP address" % value
        )
    return str(value)


def argparse_positive_int(value):
    """Parse command line positive numeric value."""
    if not str(value).isdigit() or (int(value) <= 0):
        raise argparse.ArgumentTypeError(
            "'%s' is an invalid positive numeric value" % value
        )
    return int(value)


def iperf(value):
    """Define name and location for iperf file."""
    if str(value) == 'iperf':
        cmdo = 'iperf3'
    else:
        cmdo = os.path.realpath(value)
    return str(cmdo)


def max_y_result(value1, value2, value3, value4):
    """Maximum number for results from Y axises."""
    maxy = max(max(value1), max(value2), max(value3), max(value4))
    return maxy


def list_range(value1, value2, value3, value4):
    """Range list for MSS."""
    if value4 is None:
        lrange = np.arange(value1, value2, value3)
    else:
        lrange = value4
    return lrange


def add_to_csv(
            prot, x_1, y_1, y_2, lost_r, lost_t, jitter_ms_r, jitter_ms_t,
            tr_packets_r, tr_packets_t, scv_filename
            ):
    """Add results to CSV file."""
    datacsv = pd.DataFrame()
    datacsv['Packet size'] = x_1
    datacsv['Download'] = y_1
    datacsv['Upload'] = y_2
    if prot == 'udp':
        datacsv['R Lost in procent'] = lost_r
        datacsv['T Lost in procent'] = lost_t
        datacsv['R Jitter'] = jitter_ms_r
        datacsv['T Jitter'] = jitter_ms_t
        datacsv['Packets received on Client'] = tr_packets_r
        datacsv['Packets received on Backend'] = tr_packets_t
    datacsv.to_csv(scv_filename, index=False)


def get_options(args):
    """Parse command line options."""
    parser = argparse.ArgumentParser(description="Performance test.")
    parser.add_argument(
        "--target", default='127.0.0.1', type=argparse_hostname_or_ip,
        help="destination")
    parser.add_argument(
        "-s", "--streams", default=1, type=argparse_positive_int,
        help="number of parallel test streams (default is 1)"
    )
    parser.add_argument(
        "-o", "--output", required=True,
        help="output file name"
    )
    parser.add_argument(
        "--test-time", default=5, type=argparse_positive_int,
        help="test duration in seconds (default is 5)"
    )
    parser.add_argument(
        "--interval", default=100, type=argparse_positive_int,
        help="MSS interval increment (default is 100)"
    )
    parser.add_argument(
        "--range-from", default=100, type=argparse_positive_int,
        help="MSS range start (default is 100)"
    )
    parser.add_argument(
        "--range-to", default=1500, type=argparse_positive_int,
        help="MSS range end (default is 1500)"
    )
    parser.add_argument(
        "--repeat", default=1, type=argparse_positive_int,
        help="Number of times to run the same test (default is 1)"
    )
    parser.add_argument(
        "-p", "--protocol", required=False, default='tcp', type=str,
        choices=["tcp", "udp"],
        help="Protocol usage for streaming traffic: tcp or udp (default tcp)."
    )
    parser.add_argument(
        "--iperf-file", required=False, default='iperf', type=str,
        help=("""Set custom name for iperf file, file should be in directory
        where python script. By default will using
        preinstalled iperf3 with system path""")
    )
    parser.add_argument(
        "--list-mss", required=False, nargs='+', type=int,
        help="MSS list. Ex: 650 800 1400"
    )

    options = parser.parse_args(args)
    if options.range_from > options.range_to:
        print(
            "invalid rage from/to order: [%s, %s]" % (
                str(options.range_from),
                str(options.range_to)
            )
        )
        sys.exit(-1)
    return options


def main():
    """Run main application function."""
    options = get_options(sys.argv[1:])
    stream_count = options.streams
    test_name = options.output
    curtime = get_curtime()
    host = options.target
    prot = options.protocol
    iperffile = options.iperf_file

    filename = foldername() + test_name + curtime + '.txt'
    scv_filename = foldername() + test_name + curtime + '.csv'
    png_filename = foldername() + test_name + curtime + '.png'

    # List numbers for packet sizes
    # e.g. range numbers in array betwen 100 and 1500 across 50:
    psize = list_range(
        options.range_from, options.range_to,
        options.interval, options.list_mss
    )

    clean_txt_file(filename)
    add_line(filename, 'Packet_Size', 'Mbps')

    # Plot data structure
    data = {
        'listrx': [],
        'listry': [],
        'listtx': [],
        'listty': [],
        'listarx': [],
        'listary': [],
        'listatx': [],
        'listaty': [],
        'listprocentr': [],
        'listprocentt': [],
        'listjitter_ms_r': [],
        'listjitter_ms_t': [],
        'tr_packets_r': [],
        'tr_packets_t': []

    }

    # Run iPerf in Download mode for each packet size listed in psize list
    cmd = getcmd(
        host, psize, options.test_time, stream_count,
        True, prot, iperffile
    )
    print('', cmd)
    add_line(
        filename, 'command for run iperf',
        cmd
    )
    add_line(filename, 'Download', 'traffic')
    for blks in psize:
        listary = 0
        cmd = getcmd(
            host, blks, options.test_time, stream_count,
            True, prot, iperffile
        )
        for _again in range(options.repeat):
            if prot == 'udp':
                runudp(filename, data, blks, cmd, True, options.test_time)
            else:
                runtcp(filename, data, blks, cmd, True)
            listary += (data['listry'][-1]) / options.repeat
        data['listarx'].append(data['listrx'][-1])
        data['listary'].append(listary)

    # Run iPerf in Upload mode for each packet size listed in psize list
    cmd = getcmd(
        host, psize, options.test_time, stream_count,
        False, prot, iperffile
    )
    print('\n', cmd)
    add_line(
        filename, 'Command for run iperf',
        cmd
    )
    add_line(filename, 'Upload', 'traffic')
    for blks in psize:
        listaty = 0
        cmd = getcmd(
            host, blks, options.test_time, stream_count,
            False, prot, iperffile
        )
        for _again in range(options.repeat):
            if prot == 'udp':
                runudp(filename, data, blks, cmd, False, options.test_time)
            else:
                runtcp(filename, data, blks, cmd, False)
            listaty += (data['listty'][-1]) / options.repeat
        data['listatx'].append(data['listtx'][-1])
        data['listaty'].append(listaty)

    # Define maximum result for Y axis
    max_y = max_y_result(
        data['listry'], data['listty'],
        data['listary'], data['listaty']
        )

    # Crate graph
    graph(
        png_filename,
        data['listrx'],
        data['listry'],
        data['listtx'],
        data['listty'],
        data['listarx'],
        data['listary'],
        data['listatx'],
        data['listaty'],
        test_name,
        max_y
    )

    # Add results to CSV table
    add_to_csv(
        prot,
        data['listrx'],
        data['listry'],
        data['listty'],
        data['listprocentr'],
        data['listprocentt'],
        data['listjitter_ms_r'],
        data['listjitter_ms_t'],
        data['tr_packets_r'],
        data['tr_packets_t'],
        scv_filename
    )


if __name__ == "__main__":
    # execute only if run as a script
    main()
