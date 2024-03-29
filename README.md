# Python script for the network performance measurement tool "iPerf3"

The cross-platform tool can run iperf3 bin file with options on OS: `Linux`, `macOS` and `Windows` clients.

Script can run all native options for iperf tool, parallel running, repeating for get average result. 
Implemented output in table and graph format

### Requirements

* `iperf3` tool (apt install iperf3)
* Python vesion 3
* python libraries

       matplotlib
       numpy
       argparse
       pandas

### Usage
	Install on both said Client/Server iPerf3 tool
 	Put python script on Client side
	
	On server side run iPerf3 with optional -s -J
	Where -s is running in server mode, -J make output result in json format

    On Client:
    	usage: run.py [-h] [--target TARGET] [-s STREAMS] -o OUTPUT [--test-time TEST_TIME] [--interval INTERVAL] [--range-from RANGE_FROM] [--range-to RANGE_TO] [--repeat REPEAT] [-p {tcp,udp}]

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
