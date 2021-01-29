import base64
import json
import logging
import queue
import threading
import time
import zlib

import hyperloglog
import pydantic
import requests


logging.basicConfig(level=logging.INFO)


SECOND = 1
MINUTE = 60
HOUR = 60 * MINUTE

COLLECTOR_URL = 'http://131.180.27.189:3322/tracker/report'
REPORTING_INTERVAL = 120 * SECOND
MAX_QUEUE_SIZE = 100000
COUNTER_ERROR_RATE = 0.01
COUNTER_WINDOW = HOUR

MAX_INTRO_REQUESTS_COUNT_VALUE = 2 ** 31

start_time = time.time()


class ReporterSettings(pydantic.BaseSettings):
    collector_url: str = pydantic.Field(COLLECTOR_URL)
    reporting_interval: float = pydantic.Field(REPORTING_INTERVAL)
    max_queue_size: int = pydantic.Field(MAX_QUEUE_SIZE)
    counter_error_rate: float = pydantic.Field(COUNTER_ERROR_RATE)
    counter_window: int = pydantic.Field(COUNTER_WINDOW)

    class Config:
        env_file = '.env'
        env_prefix = 'trackermetricsreporter_'


class Record:
    __slots__ = ['t', 'peer_key', 'address']
    def __init__(self, t, peer_key, address):
        self.t = t
        self.peer_key = peer_key
        self.address = address


class MetricsReporter:
    def __init__(self, listen_port, settings: ReporterSettings = None):
        self.listen_port = listen_port
        if settings is None:
            settings = ReporterSettings()
        self.settings = settings
        self.intro_requests_count = 0
        self.peers = self.new_counter()
        self.addresses = self.new_counter()
        self.lock = threading.Lock()
        self.queue = queue.Queue()
        self.input_thread = InputThread(self)
        self.output_thread = OutputThread(self)
        self.exiting = threading.Event()
        self.finished = False

    def start(self):
        logging.info('Starting MetricsReporter input & output threads')
        self.input_thread.start()
        self.output_thread.start()

    def shutdown(self):
        logging.info('Shutting down MetricsReporter...')
        self.exiting.set()
        self.queue.put(None)
        self.input_thread.join()
        self.output_thread.join()
        logging.info('MetricsReporter shutdown complete')
        self.finished = True

    def new_counter(self):
        error_rate = self.settings.counter_error_rate
        window = self.settings.counter_window
        return hyperloglog.SlidingHyperLogLog(error_rate, window)

    def count_peer(self, peer_key, address, service_id):
        if self.exiting.is_set():
            return

        if self.queue.qsize() > self.settings.max_queue_size:
            self.exiting.set()
            logging.error('MetricsReporter: Max queue size exceeded')
            return

        # Use int for lower serialization size, seconds time precision is enough
        t = int(time.time())
        self.queue.put(Record(t, peer_key, address))

    def _record(self, record):
        # Called from InputThread

        peer_str = repr(record.peer_key)
        address_str = repr(record.address)

        with self.lock:
            if self.intro_requests_count >= MAX_INTRO_REQUESTS_COUNT_VALUE:
                self.intro_requests_count = 0
            self.intro_requests_count += 1
            self.peers.add(record.t, peer_str)
            self.addresses.add(record.t, address_str)

    def _prepare_data(self):
        # Called from OutputThread

        with self.lock:
            t = time.time()
            peer_count = self.peers.card(t)
            address_count = self.addresses.card(t)

            # Items of LPFM are immutable, so deep copy is not required
            peers = self.peers.LPFM.copy()
            addresses = self.addresses.LPFM.copy()

            result = dict(
                uptime=time.time()-start_time,
                intro_requests_count=self.intro_requests_count,
                shll_counters=dict(peers=peers, addresses=addresses),
                shll_cardinalities=dict(peers=peer_count, addresses=address_count)
            )
        return result

    def _send_data(self, data):
        # Called from OutputThread

        s = json.dumps(data)
        compressed = zlib.compress(s.encode('utf-8'))
        encoded = base64.b64encode(compressed).decode('ascii')

        logging.info("Preparing data. Raw JSON size: %d, compressed size: %d",
                     len(s), len(encoded))

        try:
            t = time.time()
            requests.post(self.settings.collector_url, json={
                'port': self.listen_port,
                'compressed_data': encoded
            })
            logging.info('Post metrics to `%s` in %.4f seconds',
                         self.settings.collector_url, time.time() - t)
        except Exception as e:
            # No traceback logging to prevent excessive log spam
            logging.error("MetricsReporter %d: %s: %s",
                          self.listen_port, type(e).__name__, e)


class InputThread(threading.Thread):
    def __init__(self, reporter: MetricsReporter):
        super().__init__(name='MetricsReporterInput%s' % reporter.listen_port)
        self.reporter = reporter

    def run(self):
        logging.info('Starting thread %s', self.name)
        try:
            while True:
                try:
                    record = self.reporter.queue.get_nowait()
                except queue.Empty:
                    logging.debug('Waiting in thread %s', self.name)
                    record = self.reporter.queue.get()

                if record is None:
                    break

                self.reporter._record(record)

        except Exception as e:
            logging.exception('%s: %s: %s', self.name, type(e).__name__, e)
            self.reporter.exiting.set()

        logging.info('Finishing thread %s', self.name)


class OutputThread(threading.Thread):
    def __init__(self, reporter: MetricsReporter):
        super().__init__(name='MetricsReporterOutput%s' % reporter.listen_port)
        self.reporter = reporter

    def run(self):
        logging.info('Starting thread %s', self.name)
        try:
            while True:
                logging.debug('Waiting in thread %s', self.name)

                interval = self.reporter.settings.reporting_interval
                exiting = self.reporter.exiting.wait(interval)
                if exiting:
                    break

                data = self.reporter._prepare_data()
                self.reporter._send_data(data)

        except Exception as e:
            logging.exception('%s: %s: %s', self.name, type(e).__name__, e)
            self.reporter.exiting.set()

        logging.info('Finishing thread %s', self.name)
