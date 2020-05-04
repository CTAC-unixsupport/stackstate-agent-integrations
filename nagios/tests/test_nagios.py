# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import tempfile
import time

import mock
from pynag.Utils import misc

from stackstate_checks.base import ensure_bytes
from stackstate_checks.base.stubs import topology
from stackstate_checks.nagios import NagiosCheck

from .common import (
    CHECK_NAME,
    NAGIOS_TEST_LOG, NAGIOS_TEST_HOST_CFG, NAGIOS_TEST_SVC_TEMPLATE, NAGIOS_TEST_HOST_TEMPLATE
)


class TestEventLogTailer:
    def test_line_parser(self, aggregator):
        """
        Parse lines
        """

        # Get the config
        config, nagios_cfg = get_config(
            '\n'.join(["log_file={0}".format(NAGIOS_TEST_LOG)]),
            events=True
        )

        # Set up the check
        nagios = NagiosCheck(CHECK_NAME, {}, {}, instances=config['instances'])
        nagios.get_topology = mocked_topology

        # Run the check once
        nagios.check(config['instances'][0])

        nagios_tailer = nagios.nagios_tails[nagios_cfg.name][0]
        counters = {}

        for line in open(NAGIOS_TEST_LOG).readlines():
            parsed = nagios_tailer._parse_line(line)
            if parsed:
                event = aggregator.events[-1]
                t = event["event_type"]
                assert t in line
                assert int(event["timestamp"]) > 0, line
                assert event["host"] is not None, line
                counters[t] = counters.get(t, 0) + 1

                if t == "SERVICE ALERT":
                    assert event["event_soft_hard"] in ("SOFT", "HARD"), line
                    assert event["event_state"] in ("CRITICAL", "WARNING", "UNKNOWN", "OK"), line
                    assert event["check_name"] is not None
                elif t == "SERVICE NOTIFICATION":
                    assert event["event_state"] in (
                        "ACKNOWLEDGEMENT", "OK", "CRITICAL", "WARNING", "ACKNOWLEDGEMENT (CRITICAL)"), line
                elif t == "SERVICE FLAPPING ALERT":
                    assert event["flap_start_stop"] in ("STARTED", "STOPPED"), line
                    assert event["check_name"] is not None
                elif t == "ACKNOWLEDGE_SVC_PROBLEM":
                    assert event["check_name"] is not None
                    assert event["ack_author"] is not None
                    assert int(event["sticky_ack"]) >= 0
                    assert int(event["notify_ack"]) >= 0
                elif t == "ACKNOWLEDGE_HOST_PROBLEM":
                    assert event["ack_author"] is not None
                    assert int(event["sticky_ack"]) >= 0
                    assert int(event["notify_ack"]) >= 0
                elif t == "HOST DOWNTIME ALERT":
                    assert event["host"] is not None
                    assert event["downtime_start_stop"] in ("STARTED", "STOPPED")

        assert counters["SERVICE ALERT"] == 301
        assert counters["SERVICE NOTIFICATION"] == 120
        assert counters["HOST ALERT"] == 3
        assert counters["SERVICE FLAPPING ALERT"] == 7
        assert counters["CURRENT HOST STATE"] == 8
        assert counters["CURRENT SERVICE STATE"] == 52
        assert counters["SERVICE DOWNTIME ALERT"] == 3
        assert counters["HOST DOWNTIME ALERT"] == 5
        assert counters["ACKNOWLEDGE_SVC_PROBLEM"] == 4
        assert "ACKNOWLEDGE_HOST_PROBLEM" not in counters

    def test_continuous_bulk_parsing(self, aggregator):
        """
        Make sure the Tailer continues to parse Nagios as the file grows
        """
        test_data = open(NAGIOS_TEST_LOG).read()
        events = []
        ITERATIONS = 10
        log_file = tempfile.NamedTemporaryFile(mode="a+b")
        log_file.write(test_data.encode('utf-8'))
        log_file.flush()

        # Get the config
        config, nagios_cfg = get_config('\n'.join(["log_file={0}".format(log_file.name)]), events=True)

        # Set up the check
        nagios = NagiosCheck(CHECK_NAME, {}, {}, instances=config['instances'])
        nagios.get_topology = mocked_topology

        for i in range(ITERATIONS):
            log_file.write(test_data.encode('utf-8'))
            log_file.flush()
            nagios.check(config['instances'][0])
            events.extend(events)

        log_file.close()
        assert len(aggregator.events) == ITERATIONS * 503


class TestPerfDataTailer:
    POINT_TIME = (int(time.time()) / 15) * 15

    DB_LOG_SERVICEPERFDATA = [
        "time=0.06",
        "db0=33;180;190;0;200",
        "db1=1;150;190;0;200",
        "db2=0;120;290;1;200",
        "db3=0;110;195;5;100",
    ]

    DB_LOG_DATA = [
        "DATATYPE::SERVICEPERFDATA",
        "TIMET::{}".format(POINT_TIME),
        "HOSTNAME::myhost0",
        "SERVICEDESC::Pgsql Backends",
        "SERVICEPERFDATA::" + " ".join(DB_LOG_SERVICEPERFDATA),
        "SERVICECHECKCOMMAND::check_nrpe_1arg!check_postgres_backends",
        "HOSTSTATE::UP",
        "HOSTSTATETYPE::HARD",
        "SERVICESTATE::OK",
        "SERVICESTATETYPE::HARD",
    ]

    DISK_LOG_SERVICEPERFDATA = [
        "/=5477MB;6450;7256;0;8063",
        "/dev=0MB;2970;3341;0;3713",
        "/dev/shm=0MB;3080;3465;0;3851",
        "/var/run=0MB;3080;3465;0;3851",
        "/var/lock=0MB;3080;3465;0;3851",
        "/lib/init/rw=0MB;3080;3465;0;3851",
        "/mnt=290MB;338636;380966;0;423296",
        "/data=39812MB;40940;46057;0;51175",
    ]

    DISK_LOG_DATA = [
        "DATATYPE::SERVICEPERFDATA",
        "TIMET::{}".format(POINT_TIME),
        "HOSTNAME::myhost2",
        "SERVICEDESC::Disk Space",
        "SERVICEPERFDATA::" + " ".join(DISK_LOG_SERVICEPERFDATA),
        "SERVICECHECKCOMMAND::check_all_disks!20%!10%",
        "HOSTSTATE::UP",
        "HOSTSTATETYPE::HARD",
        "SERVICESTATE::OK",
        "SERVICESTATETYPE::HARD",
    ]

    HOST_LOG_SERVICEPERFDATA = ["rta=0.978000ms;5000.000000;5000.000000;0.000000", "pl=0%;100;100;0"]

    HOST_LOG_DATA = [
        "DATATYPE::HOSTPERFDATA",
        "TIMET::{}".format(POINT_TIME),
        "HOSTNAME::myhost1",
        "HOSTPERFDATA::" + " ".join(HOST_LOG_SERVICEPERFDATA),
        "HOSTCHECKCOMMAND::check-host-alive",
        "HOSTSTATE::UP",
        "HOSTSTATETYPE::HARD",
    ]

    def _write_log(self, log_data):
        """
        Write log data to log file
        """
        # for data in log_data:
        #     self.log_file.write("{}\n".format(data).encode('utf-8'))
        self.log_file.write("{}\n".format(log_data).encode('utf-8'))
        self.log_file.flush()

    def test_service_perfdata(self, aggregator):
        """
        Collect Nagios Service PerfData metrics
        """
        self.log_file = tempfile.NamedTemporaryFile()

        config, _ = get_config(
            "service_perfdata_file={}\n"
            "service_perfdata_file_template={}".format(self.log_file.name, NAGIOS_TEST_SVC_TEMPLATE),
            service_perf=True
        )

        # Set up the check
        nagios = NagiosCheck(CHECK_NAME, {}, {}, instances=config['instances'])
        nagios.get_topology = mocked_topology

        # Run the check once
        nagios.check(config['instances'][0])

        # Write content to log file and run check
        self._write_log('\t'.join(self.DB_LOG_DATA))
        nagios.check(config['instances'][0])

        # Test metrics
        for metric_data in self.DB_LOG_SERVICEPERFDATA:
            name, info = metric_data.split("=")
            metric_name = "nagios.pgsql_backends." + name

            values = info.split(";")
            value = float(values[0])
            expected_tags = []
            if len(values) == 5:
                expected_tags.append('warn:' + values[1])
                expected_tags.append('crit:' + values[2])
                expected_tags.append('min:' + values[3])
                expected_tags.append('max:' + values[4])

            aggregator.assert_metric(metric_name, value=value, tags=expected_tags, count=1)

        aggregator.assert_all_metrics_covered()

    def test_service_perfdata_special_cases(self, aggregator):
        """
        Handle special cases in PerfData metrics
        """
        self.log_file = tempfile.NamedTemporaryFile()

        config, _ = get_config(
            "service_perfdata_file={}\n"
            "service_perfdata_file_template={}".format(self.log_file.name, NAGIOS_TEST_SVC_TEMPLATE),
            service_perf=True
        )

        # Set up the check
        nagios = NagiosCheck(CHECK_NAME, {}, {}, instances=config['instances'])
        nagios.get_topology = mocked_topology

        # Run the check once
        nagios.check(config['instances'][0])

        # Write content to log file and run check
        self._write_log('\t'.join(self.DISK_LOG_DATA))
        nagios.check(config['instances'][0])

        # Test metrics
        for metric_data in self.DISK_LOG_SERVICEPERFDATA:
            name, info = metric_data.split("=")
            values = info.split(";")
            value = float(values[0][:-2])
            expected_tags = ['device:' + name, 'unit:' + values[0][-2:]]
            if len(values) == 5:
                expected_tags.append('warn:' + values[1])
                expected_tags.append('crit:' + values[2])
                expected_tags.append('min:' + values[3])
                expected_tags.append('max:' + values[4])

            aggregator.assert_metric("nagios.disk_space", value=value, tags=expected_tags, count=1)

        aggregator.assert_all_metrics_covered()

    def test_host_perfdata(self, aggregator):
        """
        Collect Nagios Host PerfData metrics
        """
        self.log_file = tempfile.NamedTemporaryFile()

        # Get the config
        config, _ = get_config(
            "host_perfdata_file={}\n"
            "host_perfdata_file_template={}".format(self.log_file.name, NAGIOS_TEST_HOST_TEMPLATE),
            host_perf=True
        )

        # Set up the check
        nagios = NagiosCheck(CHECK_NAME, {}, {}, config['instances'])
        nagios.get_topology = mocked_topology

        # Run the check once
        nagios.check(config['instances'][0])

        # Write content to log file and run check
        self._write_log('\t'.join(self.HOST_LOG_DATA))
        nagios.check(config['instances'][0])

        # Test metric
        for metric_data in self.HOST_LOG_SERVICEPERFDATA:
            name, info = metric_data.split("=")
            metric_name = "nagios.host." + name

            values = info.split(";")

            index = values[0].find("ms") if values[0].find("ms") != -1 else values[0].find("%")
            index = len(values[0]) - index
            value = float(values[0][:-index])
            expected_tags = ['unit:' + values[0][-index:]]
            if len(values) == 4:
                expected_tags.append('warn:' + values[1])
                expected_tags.append('crit:' + values[2])
                expected_tags.append('min:' + values[3])

            aggregator.assert_metric(metric_name, value=value, tags=expected_tags, count=1)

        aggregator.assert_all_metrics_covered()


class TestNagiosTopology:

    def test_get_topology(self, dummy_instance):
        """
        Collect Nagios Host components as topology
        """
        instance_key = {"type": "nagios", "url": "192.1.1.1", "conf_path": dummy_instance.get("nagios_conf")}

        # Mock parse_nagios_config
        NagiosCheck.parse_nagios_config = mock.MagicMock()
        NagiosCheck.parse_nagios_config.return_value = {"key": "value"}

        # Set up the check
        nagios = NagiosCheck(CHECK_NAME, {}, {}, instances=[dummy_instance])

        # Creates a fake nagios environment with minimal configs in /tmp/
        environment = misc.FakeNagiosEnvironment()
        # Create temporary director with minimal config and one by default host 'ok_host'
        environment.create_minimal_environment()
        # Update the global variables in pynag.Model
        environment.update_model()

        environment.import_config(NAGIOS_TEST_HOST_CFG)
        environment.config.parse_maincfg()

        nagios.get_topology(instance_key)
        snapshot = topology.get_snapshot(nagios.check_id)

        # topology should return 3 components, 2 from cfg and 1 default
        assert len(snapshot.get('components')) == 3

        # topology should return 1st host name as components from host.cfg
        assert snapshot.get('components')[0].get('id') == 'prod-api-1'


def get_config(nagios_conf, events=False, service_perf=False, host_perf=False):
    """
    Helper to generate a valid Nagios configuration
    """
    nagios_conf = ensure_bytes(nagios_conf)

    nagios_cfg_file = tempfile.NamedTemporaryFile(mode="a+b")
    nagios_cfg_file.write(nagios_conf)
    nagios_cfg_file.flush()

    config = {
        'instances': [
            {
                'nagios_conf': nagios_cfg_file.name,
                'collect_events': events,
                'collect_service_performance_data': service_perf,
                'collect_host_performance_data': host_perf
            }
        ]
    }

    return config, nagios_cfg_file


def mocked_topology(*args, **kwargs):
    """
    return mocked topology
    """
    return {'instance': {'key': 'dummy'}, 'components': []}
