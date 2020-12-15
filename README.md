# trackermetricsreporter

Report anonymized metrics from IPv8 trackers

This module collects two kinds of anonymized data from the IPv8 tracker:
- number of unique peers
- number of unique addresses

The data are collected using HyperLogLog counters for data streams
with a sliding time window. It allows collecting the number of unique
peers & addresses in an hour-long time window.

The benefits of HyperLogLog counters are the following:
- It allows to use of limited memory to count the arbitrarily big number
  of items with high precision;
- Data are anonymized, it is not possible to extract specific peers & addresses
  from HyperLogLog counter;
- It is possible to combine data from multiple HyperLogLog counters together,
  which allows combining the number of unique peers & addresses from multiple
  bootstrap nodes.

The module was designed to have minimal overhead on the IPv8 event loop.
For that, two separate threads are launched:
- The first thread adds new data to HyperLogLog counters;
- The second thread serializes content of HyperLogLog counters as JSON,
  compresses it, and sends it to the collector server, which combines
  multiple HyperLogLogs together.
