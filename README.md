# Script for network performance measurement and tuning with iperf3.

It is a cross-platform tool that can run on `Linux`, `macOS` and `Windows` clients.

Script communicate with backend where iperf3 runs.

### Requirements

* `iperf3`
* `python3`
* python libraries

       matplotlib
       numpy
       argparse
       pandas

   You can find more details at [requrenments.txt](requrenments.txt) file.

You need to install `iperf3` on both client and server.

To start iperf3 on a server you can run:

    iperf3 -s -J

To install python dependency on a client you can run:

    pip3 install -r requirements.txt

### Usage

    usage: run.py [-h] [--target TARGET] [-s STREAMS] -o OUTPUT [--test-time TEST_TIME] [--interval INTERVAL] [--range-from RANGE_FROM] [--range-to RANGE_TO] [--repeat REPEAT] [-p {tcp,udp}]

    Performance test.

    optional arguments:
    -h, --help            show this help message and exit
    --target TARGET       destination
    -s STREAMS, --streams STREAMS
                          number of parallel test streams (default is 1)
    -o OUTPUT, --output OUTPUT
                          output file name
    --test-time TEST_TIME
                          test duration in seconds (default is 10)
    --interval INTERVAL   MSS interval increment (default is 50)
    --range-from RANGE_FROM
                          MSS range start (default is 100)
    --range-to RANGE_TO   MSS range end (default is 1500)
    -p {tcp,udp}, --protocol {tcp,udp}
                          Protocol usage for streaming traffic: tcp or udp (default tcp).
    --iperf-file, IPERF_FILE
                          Set custom name for iperf file, otherwise will using system iperf
    --list-mss, LIST_MSS  List numbers for set MSS. Ex:(400 800 1400)
    
For example, to run performance test on a client you can run:

    python3 run.py --target server --udp --output UDP_TEST
    python3 run.py --target server --tcp -s 4 --output TCP_TEST
