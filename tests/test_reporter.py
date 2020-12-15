import threading

import pytest

from trackermetricsreporter import MetricsReporter, ReporterSettings, SECOND


class TestPeer:
    def __init__(self, mid):
        self.mid = mid


def test_reporter_1():
    reporter = MetricsReporter(1234)
    reporter.start()
    reporter.shutdown()
    assert reporter.finished


def test_reporter_2():
    settings = ReporterSettings(reporting_interval=0.1 * SECOND,
                                collector_url='')

    reporter = MetricsReporter(1234, settings)
    reporter.start()

    for i in range(10):
        reporter.count_peer(TestPeer(f"Peer{i}"), f"Address{i}", f"Service{i}")

    data_was_sent = threading.Event()
    prepared_data = []

    def send_data(data):
        prepared_data.append(data)
        data_was_sent.set()

    reporter._send_data = send_data

    data_was_sent.wait(SECOND)

    assert data_was_sent.is_set()
    assert len(prepared_data) == 1

    data = prepared_data[0]
    assert data['peer_count'] == pytest.approx(10, abs=0.1)
    assert data['address_count'] == pytest.approx(10, abs=0.1)

    reporter.shutdown()
    assert reporter.finished
