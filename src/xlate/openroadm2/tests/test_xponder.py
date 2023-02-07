import asyncio
import itertools
import logging
import time
import unittest
from multiprocessing import Process, Queue

import libyang
import sysrepo
from goldstone.lib.core import *
from goldstone.xlate.openroadm.device import DeviceServer, or_port_lookup
from goldstone.xlate.openroadm.main import load_operational_modes

from .lib import *
from .test_platform import *


class TestTransponderServer(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        logging.basicConfig(level=logging.DEBUG)
        self.conn = sysrepo.SysrepoConnection()

        with self.conn.start_session() as sess:
            sess.switch_datastore("running")
            sess.replace_config({}, "goldstone-transponder")
            sess.replace_config({}, "goldstone-platform")
            sess.replace_config({}, "org-openroadm-device")
            sess.apply_changes()

        self.server = DeviceServer(
            self.conn,
            load_operational_modes(OPERATIONAL_MODES_PATH),
            reconciliation_interval=1,
        )
        self.processes = []

        for target in (run_mock_gs_platformserver, run_mock_gs_transponderserver):
            q = Queue()
            self.processes.append((Process(target=target, args=(q,)), q))

        for process, q in self.processes:
            process.start()

        servers = [self.server]

        self.tasks = list(
            itertools.chain.from_iterable([await s.start() for s in servers])
        )

    async def test_get_mock(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                sess.switch_datastore("operational")

                # ensure goldstone-transponder is mocked by MockGSTransponderServer
                data = sess.get_data("/goldstone-transponder:modules")
                data = libyang.xpath_get(
                    data, "/goldstone-transponder:modules/module[name='piu1']/name"
                )
                self.assertEqual(data, "piu1")

        self.tasks.append(asyncio.to_thread(test))
        tasks = [
            t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
            for t in self.tasks
        ]

        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            e = task.exception()
            if e:
                raise e

    async def test_get_otsi_entries(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                # Setup basic shelf info to start with
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='SYS']/shelf-type",
                    "myshelftype",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='SYS']/administrative-state",
                    "inService",
                )
                sess.apply_changes()

                # Sets are done from running mode
                sess.switch_datastore("running")
                piu_val = "piu1"
                or_val = "or_val1"
                slot_val = 0
                setup_otsi_connections(sess, piu_val, or_val, slot_val)

                # While we are here on the first (piu1) connection, verify that manual
                # transmit power connections can be set and read back
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{or_val}']/type",
                    "org-openroadm-interfaces:otsi",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{or_val}']/administrative-state",
                    "inService",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{or_val}']/org-openroadm-optical-tributary-signal-interfaces:otsi/transmit-power",
                    "-123.46",
                )
                sess.apply_changes()

                # With the sets above, we will not see the values from the
                # operational data (these will be present on real hardware).
                # Instead we verify from the goldstone running datastore to
                # confirm correct handler functionality
                data = sess.get_data("/goldstone-transponder:modules")
                data = libyang.xpath_get(
                    data,
                    f"/goldstone-transponder:modules/module[name='{piu_val}']/network-interface[name='0']/config/output-power",
                )
                self.assertEqual(data, -123.46)

                # Also test that a subsequent modify is handled
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{or_val}']/org-openroadm-optical-tributary-signal-interfaces:otsi/transmit-power",
                    "5.43",
                )
                sess.apply_changes()

                data = sess.get_data("/goldstone-transponder:modules")
                data = libyang.xpath_get(
                    data,
                    f"/goldstone-transponder:modules/module[name='{piu_val}']/network-interface[name='{0}']/config/output-power",
                )
                self.assertEqual(data, 5.43)

                # and test that deletes are also handled
                sess.delete_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{or_val}']/org-openroadm-optical-tributary-signal-interfaces:otsi/transmit-power"
                )
                sess.apply_changes()

                data = sess.get_data("/goldstone-transponder:modules")
                data = libyang.xpath_get(
                    data,
                    f"/goldstone-transponder:modules/module[name='{piu_val}']/network-interface[name='0']/config/output-power",
                )
                self.assertEqual(data, None)

                # Now move to just testing the oper values.
                # Since this is strictly a testing environment, the values reflect the hard coded mock data values
                sess.switch_datastore("operational")
                rdata = sess.get_data("/org-openroadm-device:org-openroadm-device")
                data = libyang.xpath_get(
                    rdata,
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{or_val}']/name",
                )
                self.assertEqual(data, or_val)

                # Now move on to the next piu.  Sets are done from running mode
                sess.switch_datastore("running")
                piu_val = "piu2"
                or_val = "or_val2"
                slot_val = 0
                setup_otsi_connections(sess, piu_val, or_val, slot_val)

                # Queries are done from operational mode
                sess.switch_datastore("operational")
                rdata = sess.get_data("/org-openroadm-device:org-openroadm-device")
                data = libyang.xpath_get(
                    rdata,
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{or_val}']/name",
                )
                self.assertEqual(data, or_val)

                # Now move on to the next piu.  Sets are done from running mode
                sess.switch_datastore("running")
                piu_val = "piu3"
                or_val = "or_val3"
                slot_val = 0
                setup_otsi_connections(sess, piu_val, or_val, slot_val)

                # Queries are done from operational mode
                sess.switch_datastore("operational")
                rdata = sess.get_data("/org-openroadm-device:org-openroadm-device")
                data = libyang.xpath_get(
                    rdata,
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{or_val}']/name",
                )
                self.assertEqual(data, or_val)

                # Now move on to the next piu.  Sets are done from running mode
                sess.switch_datastore("running")
                piu_val = "piu4"
                or_val = "or_val4"
                slot_val = 0
                setup_otsi_connections(sess, piu_val, or_val, slot_val)

                # Queries are done from operational mode
                sess.switch_datastore("operational")
                rdata = sess.get_data("/org-openroadm-device:org-openroadm-device")
                data = libyang.xpath_get(
                    rdata,
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{or_val}']/name",
                )
                self.assertEqual(data, or_val)

                #
                # With the PIUs configured as above, go ahead and check the PIU responses
                # here
                #
                piu1_data = self.server.get_operational_data(
                    "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='piu1']"
                )
                piu1_expected = {
                    "circuit-pack-name": "piu1",
                    "vendor": "piu1_vendor_name",
                    "model": "piu1_vendor_pn",
                    "serial-id": "piu1_vendor_sn",
                    "operational-state": "inService",
                    "slot": "0",
                    "subSlot": "piu1",
                    "ports": [
                        {
                            "port-name": "1",
                            "operational-state": "inService",
                            "port-direction": "bidirectional",
                            "faceplate-label": "none",
                            "is-physical": True,
                        }
                    ],
                    "shelf": "SYS",
                    "administrative-state": "inService",
                    "circuit-pack-type": "cpType",
                    "is-pluggable-optics": True,
                    "is-physical": True,
                    "is-passive": False,
                    "faceplate-label": "none",
                }
                self.assertDictEqual(piu1_data[0], piu1_expected)

                piu2_data = self.server.get_operational_data(
                    "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='piu2']"
                )
                piu2_expected = {
                    "circuit-pack-name": "piu2",
                    "vendor": "piu2_vendor_name",
                    "model": "",
                    "serial-id": "",
                    "operational-state": "degraded",
                    "slot": "0",
                    "subSlot": "piu2",
                    "ports": [
                        {
                            "port-name": "1",
                            "operational-state": "inService",
                            "port-direction": "bidirectional",
                            "faceplate-label": "none",
                            "is-physical": True,
                        }
                    ],
                    "shelf": "SYS",
                    "administrative-state": "inService",
                    "circuit-pack-type": "cpType",
                    "is-pluggable-optics": True,
                    "is-physical": True,
                    "is-passive": False,
                    "faceplate-label": "none",
                }
                self.assertDictEqual(piu2_data[0], piu2_expected)

                piu3_data = self.server.get_operational_data(
                    "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='piu3']"
                )
                piu3_expected = {
                    "circuit-pack-name": "piu3",
                    "vendor": "piu3_vendor_name",
                    "model": "",
                    "serial-id": "piu3_vendor_sn",
                    "operational-state": "outOfService",
                    "slot": "0",
                    "subSlot": "piu3",
                    "ports": [
                        {
                            "port-name": "1",
                            "operational-state": "inService",
                            "port-direction": "bidirectional",
                            "faceplate-label": "none",
                            "is-physical": True,
                        }
                    ],
                    "shelf": "SYS",
                    "administrative-state": "inService",
                    "circuit-pack-type": "cpType",
                    "is-pluggable-optics": True,
                    "is-physical": True,
                    "is-passive": False,
                    "faceplate-label": "none",
                }
                self.assertDictEqual(piu3_data[0], piu3_expected)

                piu4_data = self.server.get_operational_data(
                    "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='piu4']"
                )
                piu4_expected = {
                    "circuit-pack-name": "piu4",
                    "vendor": "",
                    "model": "piu4_vendor_pn",
                    "serial-id": "",
                    "operational-state": "degraded",
                    "slot": "0",
                    "subSlot": "piu4",
                    "ports": [
                        {
                            "port-name": "1",
                            "operational-state": "inService",
                            "port-direction": "bidirectional",
                            "faceplate-label": "none",
                            "is-physical": True,
                        }
                    ],
                    "shelf": "SYS",
                    "administrative-state": "inService",
                    "circuit-pack-type": "cpType",
                    "is-pluggable-optics": True,
                    "is-physical": True,
                    "is-passive": False,
                    "faceplate-label": "none",
                }
                self.assertDictEqual(piu4_data[0], piu4_expected)

        self.tasks.append(asyncio.to_thread(test))
        tasks = [
            t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
            for t in self.tasks
        ]

        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            e = task.exception()
            if e:
                raise e

    async def test_otsi_explicit_provision(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:

                # setup 'SYS' shelf
                sess.switch_datastore("running")
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='SYS']/shelf-type",
                    "SYS",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='SYS']/administrative-state",
                    "inService",
                )

                # setup circuit-pack and interface
                setup_otsi_connections(sess, "piu1", "otsi-piu1", 1)

                # test explicit provisioning of otsi-rate, modulation-format, and fec
                piu_xpath = "/org-openroadm-device:org-openroadm-device/interface[name='otsi-piu1']"
                sess.set_item(piu_xpath + "/type", "org-openroadm-interfaces:otsi")
                sess.set_item(piu_xpath + "/administrative-state", "inService")
                sess.set_item(
                    piu_xpath
                    + "/org-openroadm-optical-tributary-signal-interfaces:otsi/provision-mode",
                    "explicit",
                )
                sess.set_item(
                    piu_xpath
                    + "/org-openroadm-optical-tributary-signal-interfaces:otsi/otsi-rate",
                    "org-openroadm-common-optical-channel-types:R100G-otsi",
                )
                sess.set_item(
                    piu_xpath
                    + "/org-openroadm-optical-tributary-signal-interfaces:otsi/modulation-format",
                    "dp-qam16",
                )
                sess.set_item(
                    piu_xpath
                    + "/org-openroadm-optical-tributary-signal-interfaces:otsi/fec",
                    "org-openroadm-common-types:ofec",
                )
                sess.apply_changes()

                sess.switch_datastore("operational")
                data = self.server.get_operational_data(
                    "/goldstone-transponder:modules/module[name='piu1']/network-interface[name='0']/config"
                )
                [data] = data
                expected = {
                    "name": "0",
                    "line-rate": "100g",
                    "modulation-format": "dp-16-qam",
                    "fec-type": "ofec",
                    "output-power": -123.456789,
                }
                self.assertDictEqual(expected, data)

                data = self.server.get_operational_data(
                    "/org-openroadm-device:org-openroadm-device/interface[name='otsi-piu1']/org-openroadm-optical-tributary-signal-interfaces:otsi"
                )
                [data] = data
                expected = {
                    "provision-mode": "explicit",
                    "otsi-rate": "org-openroadm-common-optical-channel-types:R100G-otsi",
                    "fec": "org-openroadm-common-types:ofec",
                    "modulation-format": "dp-qam16",
                }
                self.assertDictEqual(expected, data)

                # test deletion
                sess.switch_datastore("running")
                sess.delete_item(
                    "/org-openroadm-device:org-openroadm-device/interface[name='otsi-piu1']"
                )
                sess.apply_changes()

                sess.switch_datastore("operational")
                data = self.server.get_operational_data(
                    "/org-openroadm-device:org-openroadm-device/interface[name='otsi-piu1']",
                    default=None,
                )
                self.assertEqual(None, data)

        self.tasks.append(asyncio.to_thread(test))
        tasks = [
            t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
            for t in self.tasks
        ]

        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            e = task.exception()
            if e:
                raise e

    async def test_set_opt_oper_mode(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:

                # setup 'SYS' shelf
                sess.switch_datastore("running")
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='SYS']/shelf-type",
                    "SYS",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='SYS']/administrative-state",
                    "inService",
                )

                # setup circuit-pack and interface
                setup_otsi_connections(sess, "piu1", "piu1", 1)

                # test non-existent profile
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='piu1']/type",
                    "org-openroadm-interfaces:otsi",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='piu1']/administrative-state",
                    "inService",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='piu1']/org-openroadm-optical-tributary-signal-interfaces:otsi/provision-mode",
                    "profile",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='piu1']/org-openroadm-optical-tributary-signal-interfaces:otsi/optical-operational-mode",
                    "foo",
                )
                self.assertRaises(
                    sysrepo.errors.SysrepoCallbackFailedError, sess.apply_changes
                )
                sess.discard_changes()

                # test ORBKD-W-400G-1000X profile
                sess.switch_datastore("running")
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='piu1']/type",
                    "org-openroadm-interfaces:otsi",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='piu1']/administrative-state",
                    "inService",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='piu1']/org-openroadm-optical-tributary-signal-interfaces:otsi/provision-mode",
                    "profile",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='piu1']/org-openroadm-optical-tributary-signal-interfaces:otsi/optical-operational-mode",
                    "ORBKD-W-400G-1000X",
                )
                sess.apply_changes()

                sess.switch_datastore("operational")
                data = self.server.get_operational_data(
                    "/goldstone-transponder:modules/module[name='piu1']/network-interface[name='0']/config"
                )
                [data] = data
                expected = {
                    "name": "0",
                    "line-rate": "400g",
                    "modulation-format": "dp-16-qam-ps",
                    "fec-type": "ofec",
                    "output-power": -123.456789,
                }
                self.assertDictEqual(expected, data)

                data = self.server.get_operational_data(
                    "/org-openroadm-device:org-openroadm-device/interface[name='piu1']/org-openroadm-optical-tributary-signal-interfaces:otsi"
                )
                [data] = data
                expected = {
                    "provision-mode": "profile",
                    "optical-operational-mode": "ORBKD-W-400G-1000X",
                }
                self.assertDictEqual(expected, data)

                # test deletion
                sess.switch_datastore("running")
                sess.delete_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='piu1']/org-openroadm-optical-tributary-signal-interfaces:otsi/optical-operational-mode"
                )
                sess.apply_changes()

                sess.switch_datastore("operational")
                [data] = self.server.get_operational_data(
                    "/goldstone-transponder:modules/module[name='piu1']/network-interface[name='0']/config"
                )
                expected = {
                    "name": "0",
                    "output-power": -123.456789,
                }
                self.assertDictEqual(expected, data)

                [data] = self.server.get_operational_data(
                    "/org-openroadm-device:org-openroadm-device/interface[name='piu1']/org-openroadm-optical-tributary-signal-interfaces:otsi"
                )
                expected = {
                    "provision-mode": "profile",
                }
                self.assertDictEqual(expected, data)

        self.tasks.append(asyncio.to_thread(test))
        tasks = [
            t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
            for t in self.tasks
        ]

        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            e = task.exception()
            if e:
                raise e

    async def test_set_frequency(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:

                # setup 'SYS' shelf
                sess.switch_datastore("running")
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='SYS']/shelf-type",
                    "SYS",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='SYS']/administrative-state",
                    "inService",
                )

                # setup circuit-pack and interface
                setup_otsi_connections(sess, "piu1", "piu1", 1)

                # test set frequency
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='piu1']/org-openroadm-optical-tributary-signal-interfaces:otsi/frequency",
                    123.456,
                )
                sess.apply_changes()

                sess.switch_datastore("operational")
                data = self.server.get_operational_data(
                    "/goldstone-transponder:modules/module[name='piu1']/network-interface[name='0']/config"
                )
                [data] = data
                expected = {
                    "name": "0",
                    "tx-laser-freq": 123456000000000,
                    "output-power": -123.456789,
                }
                self.assertDictEqual(expected, data)

                # test deletion
                sess.switch_datastore("running")
                sess.delete_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='piu1']/org-openroadm-optical-tributary-signal-interfaces:otsi/frequency"
                )
                sess.apply_changes()

                sess.switch_datastore("operational")
                [data] = self.server.get_operational_data(
                    "/goldstone-transponder:modules/module[name='piu1']/network-interface[name='0']/config"
                )
                expected = {
                    "name": "0",
                    "output-power": -123.456789,
                }
                self.assertDictEqual(expected, data)

        self.tasks.append(asyncio.to_thread(test))
        tasks = [
            t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
            for t in self.tasks
        ]

        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            e = task.exception()
            if e:
                raise e

    async def test_get_client_eth_speed(self):
        def setup_eth_speed(self, sess, slot, piu, if_name, or_port, or_speed):
            setup_eth_port_config(sess, slot, piu, if_name, or_port)
            sess.set_item(
                f"/org-openroadm-device:org-openroadm-device/interface[name='{if_name}']/org-openroadm-ethernet-interfaces:ethernet/speed",
                f"{or_speed}",
            )
            sess.apply_changes()

        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:

                setup_shelf_and_sys(sess)

                # These names are from the Openroadm side
                slot = 0
                piu = "piu1"
                ifname = "or_val1_1"
                port = "port1"
                speed = 100000
                setup_eth_speed(self, sess, slot, piu, ifname, port, speed)

                # Verify that the goldstone running and openroadm operational
                # data stores have the info
                gs_piu, gs_port = or_port_lookup.get(port)
                data = self.server.get_running_data(
                    f"/goldstone-transponder:modules/module[name='{gs_piu}']/host-interface[name='{gs_port}']/config/signal-rate"
                )
                self.assertEqual(data, "100-gbe")
                data = self.server.get_operational_data(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{ifname}']/org-openroadm-ethernet-interfaces:ethernet/speed"
                )
                self.assertEqual(data[0], 100000)

                slot = 0
                piu = "piu2"
                ifname = "or_val1_2"
                port = "port5"
                speed = 200000
                setup_eth_speed(self, sess, slot, piu, ifname, port, speed)

                # Verify that the goldstone running and openroadm operational
                # data stores have the info
                gs_piu, gs_port = or_port_lookup.get(port)
                data = self.server.get_running_data(
                    f"/goldstone-transponder:modules/module[name='{gs_piu}']/host-interface[name='{gs_port}']/config/signal-rate"
                )
                self.assertEqual(data, "200-gbe")

                data = self.server.get_operational_data(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{ifname}']/org-openroadm-ethernet-interfaces:ethernet/speed"
                )
                self.assertEqual(data[0], 200000)

                slot = 0
                piu = "piu3"
                ifname = "or_val1_3"
                port = "port9"
                speed = 400000
                setup_eth_speed(self, sess, slot, piu, ifname, port, speed)

                # Verify that the goldstone running and openroadm operational
                # data stores have the info
                gs_piu, gs_port = or_port_lookup.get(port)
                data = self.server.get_running_data(
                    f"/goldstone-transponder:modules/module[name='{gs_piu}']/host-interface[name='{gs_port}']/config/signal-rate"
                )
                self.assertEqual(data, "400-gbe")
                data = self.server.get_operational_data(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{ifname}']/org-openroadm-ethernet-interfaces:ethernet/speed"
                )
                self.assertEqual(data[0], 400000)

                slot = 0
                piu = "piu1"
                ifname = "or_val1_4"
                port = "port1"
                speed = 0
                setup_eth_speed(self, sess, slot, piu, ifname, port, speed)

                # Verify that the goldstone running and openroadm operational
                # data stores have the info
                gs_piu, gs_port = or_port_lookup.get(port)
                data = self.server.get_running_data(
                    f"/goldstone-transponder:modules/module[name='{gs_piu}']/host-interface[name='{gs_port}']/config/signal-rate"
                )
                self.assertEqual(data, "unknown")
                data = self.server.get_operational_data(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{ifname}']/org-openroadm-ethernet-interfaces:ethernet"
                )
                # zero speed entries need extra help
                self.assertEqual(data[0].get("speed"), 0)

                slot = 0
                piu = "piu4"
                ifname = "or_val1_5"
                port = "port13"
                speed = 100000
                setup_eth_speed(self, sess, slot, piu, ifname, port, speed)

                # Verify that the goldstone running and openroadm operational
                # data stores have the info
                gs_piu, gs_port = or_port_lookup.get(port)
                data = self.server.get_running_data(
                    f"/goldstone-transponder:modules/module[name='{gs_piu}']/host-interface[name='{gs_port}']/config/signal-rate"
                )
                self.assertEqual(data, "100-gbe")
                data = self.server.get_operational_data(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{ifname}']/org-openroadm-ethernet-interfaces:ethernet/speed"
                )
                self.assertEqual(data[0], 100000)

                # and test that deletes are also handled
                sess.delete_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{ifname}']/org-openroadm-ethernet-interfaces:ethernet/speed"
                )
                sess.apply_changes()
                data = self.server.get_operational_data(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{ifname}']/org-openroadm-ethernet-interfaces:ethernet/speed"
                )
                self.assertEqual(data, None)

        self.tasks.append(asyncio.to_thread(test))
        tasks = [
            t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
            for t in self.tasks
        ]

        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            e = task.exception()
            if e:
                raise e

    async def test_get_client_eth_fec(self):
        def setup_eth_fec(self, sess, slot, piu, if_name, or_port, or_fec):
            setup_eth_port_config(sess, slot, piu, if_name, or_port)
            sess.set_item(
                f"/org-openroadm-device:org-openroadm-device/interface[name='{if_name}']/org-openroadm-ethernet-interfaces:ethernet/fec",
                f"{or_fec}",
            )
            sess.apply_changes()

        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:

                setup_shelf_and_sys(sess)

                # These names are from the Openroadm side
                slot = 0
                piu = "piu1"
                ifname = "or_val1_1"
                port = "port1"
                fec = "org-openroadm-common-types:off"
                setup_eth_fec(self, sess, slot, piu, ifname, port, fec)

                # Verify that the goldstone running and openroadm operational
                # data stores have the info
                gs_piu, gs_port = or_port_lookup.get(port)
                data = self.server.get_running_data(
                    f"/goldstone-transponder:modules/module[name='{gs_piu}']/host-interface[name='{gs_port}']/config/fec-type"
                )
                self.assertEqual(data, "none")
                data = self.server.get_operational_data(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{ifname}']/org-openroadm-ethernet-interfaces:ethernet/fec"
                )
                self.assertEqual(data[0], "org-openroadm-common-types:off")

                slot = 0
                piu = "piu3"
                ifname = "or_val1_9"
                port = "port1"
                fec = "org-openroadm-common-types:rsfec"
                setup_eth_fec(self, sess, slot, piu, ifname, port, fec)

                # Verify that the goldstone running and openroadm operational
                # data stores have the info
                gs_piu, gs_port = or_port_lookup.get(port)
                data = self.server.get_running_data(
                    f"/goldstone-transponder:modules/module[name='{gs_piu}']/host-interface[name='{gs_port}']/config/fec-type"
                )
                self.assertEqual(data, "rs")
                data = self.server.get_operational_data(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{ifname}']/org-openroadm-ethernet-interfaces:ethernet/fec"
                )
                self.assertEqual(data[0], "org-openroadm-common-types:rsfec")

                slot = 0
                piu = "piu4"
                ifname = "or_val1_13"
                port = "port1"
                fec = "org-openroadm-common-types:baser"
                setup_eth_fec(self, sess, slot, piu, ifname, port, fec)

                # Verify that the goldstone running and openroadm operational
                # data stores have the info
                gs_piu, gs_port = or_port_lookup.get(port)
                data = self.server.get_running_data(
                    f"/goldstone-transponder:modules/module[name='{gs_piu}']/host-interface[name='{gs_port}']/config/fec-type"
                )
                self.assertEqual(data, "fc")
                data = self.server.get_operational_data(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{ifname}']/org-openroadm-ethernet-interfaces:ethernet/fec"
                )
                self.assertEqual(data[0], "org-openroadm-common-types:baser")

                # and test that deletes are also handled
                sess.delete_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{ifname}']/org-openroadm-ethernet-interfaces:ethernet/fec"
                )
                sess.apply_changes()
                data = self.server.get_running_data(
                    f"/goldstone-transponder:modules/module[name='{gs_piu}']/host-interface[name='{gs_port}']/config/fec-type"
                )
                self.assertEqual(data, None)
                data = self.server.get_operational_data(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{ifname}']/org-openroadm-ethernet-interfaces:ethernet/fec"
                )
                self.assertEqual(data, None)

        self.tasks.append(asyncio.to_thread(test))
        tasks = [
            t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
            for t in self.tasks
        ]

        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            e = task.exception()
            if e:
                raise e

    async def test_get_client_eth_cur_speed(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                setup_shelf_and_sys(sess)

                slot = 0
                piu = "piu1"
                ifname = "or_val1_1"
                port = "port1"
                setup_eth_port_config(sess, slot, piu, ifname, port)
                # Since we are just checking RO oper data, no 'set' is required
                # values come from the mock goldstone-transponder data
                data = self.server.get_operational_data(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{ifname}']/org-openroadm-ethernet-interfaces:ethernet/curr-speed"
                )
                self.assertEqual(data[0], "100000")

                slot = 0
                piu = "piu2"
                ifname = "or_val1_6"
                port = "port5"
                setup_eth_port_config(sess, slot, piu, ifname, port)
                # Since we are just checking RO oper data, no 'set' is required
                # values come from the mock goldstone-transponder data
                data = self.server.get_operational_data(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{ifname}']/org-openroadm-ethernet-interfaces:ethernet/curr-speed"
                )
                self.assertEqual(data[0], "200000")

                slot = 0
                piu = "piu3"
                ifname = "or_val1_11"
                port = "port9"
                setup_eth_port_config(sess, slot, piu, ifname, port)
                # Since we are just checking RO oper data, no 'set' is required
                # values come from the mock goldstone-transponder data
                data = self.server.get_operational_data(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{ifname}']/org-openroadm-ethernet-interfaces:ethernet/curr-speed"
                )
                self.assertEqual(data[0], "400000")

                slot = 0
                piu = "piu4"
                ifname = "or_val1_16"
                port = "port16"
                setup_eth_port_config(sess, slot, piu, ifname, port)
                # Since we are just checking RO oper data, no 'set' is required
                # values come from the mock goldstone-transponder data
                data = self.server.get_operational_data(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='{ifname}']/org-openroadm-ethernet-interfaces:ethernet/curr-speed"
                )
                self.assertEqual(data[0], "100000")

                # Bad lookups are handled ok
                data = self.server.get_operational_data(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='foofoo']/org-openroadm-ethernet-interfaces:ethernet/curr-speed"
                )
                self.assertEqual(data, None)

                # And verify that top level get works as well
                data = self.server.get_operational_data(
                    f"/org-openroadm-device:org-openroadm-device"
                )
                p1 = libyang.xpath_get(
                    data, "interface[name='or_val1_1']/ethernet/curr-speed"
                )
                self.assertEqual(int(p1), 100000)
                p2 = libyang.xpath_get(
                    data, "interface[name='or_val1_6']/ethernet/curr-speed"
                )
                self.assertEqual(int(p2), 200000)
                p3 = libyang.xpath_get(
                    data, "interface[name='or_val1_11']/ethernet/curr-speed"
                )
                self.assertEqual(int(p3), 400000)
                p4 = libyang.xpath_get(
                    data, "interface[name='or_val1_16']/ethernet/curr-speed"
                )
                self.assertEqual(int(p4), 100000)

        self.tasks.append(asyncio.to_thread(test))
        tasks = [
            t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
            for t in self.tasks
        ]

        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            e = task.exception()
            if e:
                raise e

    async def test_otsig_write(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                # setup 'SYS' shelf
                sess.switch_datastore("running")
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='SYS']/shelf-type",
                    "SYS",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='SYS']/administrative-state",
                    "inService",
                )

                # setup circuit-pack and otsi interface
                setup_otsi_connections(sess, "piu1", "otsi-piu1", 1)

                # setup circuit-pack and otsi-g interface
                # supporting-circuit-pack-name will be derived from supporting-interface-list for high-level-interfaces in Phase 2
                setup_interface(sess, "otsig-piu1", "piu1")

                # setup supporting interface
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='otsig-piu1']/supporting-interface-list",
                    "otsi-piu1",
                )

                # test provision otsig interface
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='otsig-piu1']/type",
                    "org-openroadm-interfaces:otsi-group",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='otsig-piu1']/org-openroadm-otsi-group-interfaces:otsi-group/group-rate",
                    "org-openroadm-common-optical-channel-types:R400G-otsi",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='otsig-piu1']/org-openroadm-otsi-group-interfaces:otsi-group/group-id",
                    1,
                )
                sess.apply_changes()

                data = self.server.get_operational_data(
                    "/org-openroadm-device:org-openroadm-device/interface[name='otsig-piu1']/org-openroadm-otsi-group-interfaces:otsi-group"
                )
                [data] = data
                expected = {
                    "group-rate": "org-openroadm-common-optical-channel-types:R400G-otsi",
                    "group-id": 1,
                }
                self.assertDictEqual(expected, data)

        self.tasks.append(asyncio.to_thread(test))
        tasks = [
            t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
            for t in self.tasks
        ]

        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            e = task.exception()
            if e:
                raise e

    async def test_set_otuc_loopback(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                # setup 'SYS' shelf
                sess.switch_datastore("running")
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='SYS']/shelf-type",
                    "SYS",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='SYS']/administrative-state",
                    "inService",
                )

                # setup circuit-pack and otsi interface
                setup_otsi_connections(sess, "piu1", "otsi-piu1", 1)

                # setup circuit-pack and otsi-g interface
                # supporting-circuit-pack-name will be derived from supporting-interface-list for high-level-interfaces in Phase 2
                setup_interface(sess, "otsig-piu1", "piu1")

                # setup supporting interface connection
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='otsig-piu1']/supporting-interface-list",
                    "otsi-piu1",
                )

                # setup otuc interface
                setup_interface(sess, "otuc-piu1", "piu1")

                # setup supporting interface connection
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='otuc-piu1']/supporting-interface-list",
                    "otsig-piu1",
                )

                # test provision otuc loopback
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='otuc-piu1']/type",
                    "org-openroadm-interfaces:otnOtu",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='otuc-piu1']/org-openroadm-otn-otu-interfaces:otu/rate",
                    "org-openroadm-otn-common-types:OTUCn",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='otuc-piu1']/org-openroadm-otn-otu-interfaces:otu/otucn-n-rate",
                    4,
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='otuc-piu1']/org-openroadm-otn-otu-interfaces:otu/maint-loopback/enabled",
                    True,
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='otuc-piu1']/org-openroadm-otn-otu-interfaces:otu/maint-loopback/type",
                    "fac",
                )
                sess.apply_changes()

                sess.switch_datastore("operational")
                data = self.server.get_operational_data(
                    "/goldstone-transponder:modules/module[name='piu1']/network-interface[name='0']/config"
                )
                [data] = data
                expected = {
                    "name": "0",
                    "output-power": -123.456789,
                    "loopback-type": "shallow",
                }
                self.assertDictEqual(expected, data)

                # test enabled = false mapping
                sess.switch_datastore("running")
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='otuc-piu1']/org-openroadm-otn-otu-interfaces:otu/maint-loopback/enabled",
                    False,
                )
                sess.apply_changes()

                sess.switch_datastore("operational")
                data = self.server.get_operational_data(
                    "/goldstone-transponder:modules/module[name='piu1']/network-interface[name='0']/config"
                )
                [data] = data
                expected = {
                    "name": "0",
                    "output-power": -123.456789,
                    "loopback-type": "none",
                }
                self.assertDictEqual(expected, data)

                # test otucn interface deletion
                sess.switch_datastore("running")
                sess.delete_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='otuc-piu1']/name"
                )
                sess.apply_changes()

                data = self.server.get_running_data(
                    "/org-openroadm-device:org-openroadm-device/interface[name='otuc-piu1']"
                )
                self.assertEqual(None, data)

        self.tasks.append(asyncio.to_thread(test))
        tasks = [
            t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
            for t in self.tasks
        ]

        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            e = task.exception()
            if e:
                raise e

    async def test_set_oducn(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                sess.switch_datastore("running")

                # setup 'SYS' shelf
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='SYS']/shelf-type",
                    "SYS",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='SYS']/administrative-state",
                    "inService",
                )

                # setup circuit-pack and otsi interface
                setup_otsi_connections(sess, "piu1", "otsi-piu1", 1)

                # setup circuit-pack and otsi-g interface
                # supporting-circuit-pack-name will be derived from supporting-interface-list for high-level-interfaces in Phase 2
                setup_interface(sess, "otsig-piu1", "piu1")

                # setup supporting interface connection (otsig -> otsi)
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='otsig-piu1']/supporting-interface-list",
                    "otsi-piu1",
                )

                # setup otuc interface
                setup_interface(sess, "otuc-piu1", "piu1")

                # setup supporting interface connection (otuc -> otsig)
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='otuc-piu1']/supporting-interface-list",
                    "otsig-piu1",
                )

                # setup oduc interface
                setup_interface(sess, "oduc-piu1", "piu1")

                # setup supporting interface connection (oduc -> otuc)
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='oduc-piu1']/supporting-interface-list",
                    "otuc-piu1",
                )

                # test provision of odu
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='oduc-piu1']/type",
                    "org-openroadm-interfaces:otnOdu",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='oduc-piu1']/org-openroadm-otn-odu-interfaces:odu/rate",
                    "org-openroadm-otn-common-types:ODUCn",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='oduc-piu1']/org-openroadm-otn-odu-interfaces:odu/oducn-n-rate",
                    4,
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='oduc-piu1']/org-openroadm-otn-odu-interfaces:odu/odu-function",
                    "org-openroadm-otn-common-types:ODU-TTP",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='oduc-piu1']/org-openroadm-otn-odu-interfaces:odu/monitoring-mode",
                    "terminated",
                )

                sess.apply_changes()

                sess.switch_datastore("operational")
                data = self.server.get_operational_data(
                    "/org-openroadm-device:org-openroadm-device/interface[name='oduc-piu1']/org-openroadm-otn-odu-interfaces:odu"
                )
                [data] = data
                expected = {
                    "rate": "org-openroadm-otn-common-types:ODUCn",
                    "oducn-n-rate": 4,
                    "odu-function": "org-openroadm-otn-common-types:ODU-TTP",
                    "monitoring-mode": "terminated",
                }
                self.assertDictEqual(expected, data)

                # test deletion
                sess.switch_datastore("running")
                sess.delete_item(
                    f"/org-openroadm-device:org-openroadm-device/interface[name='oduc-piu1']"
                )
                sess.apply_changes()

                sess.switch_datastore("operational")
                data = self.server.get_operational_data(
                    "/org-openroadm-device:org-openroadm-device/interface[name='oduc-piu1']"
                )
                self.assertEqual(None, data)

        self.tasks.append(asyncio.to_thread(test))
        tasks = [
            t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
            for t in self.tasks
        ]

        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            e = task.exception()
            if e:
                raise e

    async def test_set_odu_connection(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                sess.switch_datastore("running")
                setup_interface_hierarchy(sess)
                setup_shelf_and_sys(sess)
                setup_eth_port_config(sess, 0, "piu1", "eth-1", "port1")

                # nw-odu (1 of 4 in 400G operation)
                setup_interface(
                    sess,
                    "odu-1.1",
                    "piu1",
                    type="org-openroadm-interfaces:otnOdu",
                    sup_intf="oduc-piu1",
                )
                # client-odu
                setup_interface(
                    sess,
                    "odu-client-port1",
                    "piu1",
                    type="org-openroadm-interfaces:otnOdu",
                    sup_intf="eth-1",
                )

                # required for odu-connection
                sess.set_item(
                    "/org-openroadm-device:org-openroadm-device/info/node-type", "xpdr"
                )
                sess.apply_changes()

                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/odu-connection[connection-name='test_connection']/direction",
                    "unidirectional",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/odu-connection[connection-name='test_connection']/source/src-if",
                    "odu-1.1",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/odu-connection[connection-name='test_connection']/destination/dst-if",
                    "odu-client-port1",
                )
                sess.apply_changes()

                sess.switch_datastore("operational")
                data = self.server.get_operational_data(
                    "/org-openroadm-device:org-openroadm-device/odu-connection[connection-name='test_connection']"
                )
                [data] = data
                expected = {
                    "connection-name": "test_connection",
                    "direction": "unidirectional",
                    "source": {"src-if": "odu-1.1"},
                    "destination": {"dst-if": "odu-client-port1"},
                }
                self.assertDictEqual(expected, data)

                sess.switch_datastore("running")
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/odu-connection[connection-name='test_connection_2']/direction",
                    "unidirectional",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/odu-connection[connection-name='test_connection_2']/source/src-if",
                    "odu-client-port1",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/odu-connection[connection-name='test_connection_2']/destination/dst-if",
                    "odu-1.1",
                )
                sess.apply_changes()

                sess.switch_datastore("operational")
                data = self.server.get_operational_data(
                    "/org-openroadm-device:org-openroadm-device/odu-connection[connection-name='test_connection_2']"
                )
                [data] = data
                expected = {
                    "connection-name": "test_connection_2",
                    "direction": "unidirectional",
                    "source": {"src-if": "odu-client-port1"},
                    "destination": {"dst-if": "odu-1.1"},
                }
                self.assertDictEqual(expected, data)

        self.tasks.append(asyncio.to_thread(test))
        tasks = [
            t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
            for t in self.tasks
        ]

        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            e = task.exception()
            if e:
                raise e

    async def test_odu_static_mappings(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                sess.switch_datastore("running")
                setup_interface_hierarchy(sess)
                setup_shelf_and_sys(sess)
                setup_eth_port_config(sess, 0, "piu1", "eth-1", "port1")

                # nw-odu
                setup_interface(
                    sess,
                    "odu-1.1",
                    "piu1",
                    type="org-openroadm-interfaces:otnOdu",
                    sup_intf="oduc-piu1",
                )

                sess.switch_datastore("operational")
                [data] = self.server.get_operational_data(
                    "/org-openroadm-device:org-openroadm-device/interface[name='odu-1.1']/org-openroadm-otn-odu-interfaces:odu"
                )
                expected = {
                    "no-oam-function": None,
                    "no-maint-testsignal-function": None,
                }
                self.assertDictEqual(expected, data)

                sess.switch_datastore("running")
                # client-odu
                setup_interface(
                    sess,
                    "odu-client-port1",
                    "piu1",
                    type="org-openroadm-interfaces:otnOdu",
                    sup_intf="eth-1",
                )

                sess.switch_datastore("operational")
                [data] = self.server.get_operational_data(
                    "/org-openroadm-device:org-openroadm-device/interface[name='odu-client-port1']/org-openroadm-otn-odu-interfaces:odu"
                )
                expected = {
                    "no-oam-function": None,
                    "no-maint-testsignal-function": None,
                }
                self.assertDictEqual(expected, data)

                # test deletion
                sess.switch_datastore("running")
                sess.delete_item(
                    f"/org-openroadm-device:org-openroadm-device/odu-connection[connection-name='test_connection_2']"
                )
                sess.apply_changes()

                sess.switch_datastore("operational")
                data = self.server.get_operational_data(
                    "/org-openroadm-device:org-openroadm-device/odu-connection[connection-name='test_connection_2']"
                )
                self.assertEqual(None, data)

        self.tasks.append(asyncio.to_thread(test))
        tasks = [
            t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
            for t in self.tasks
        ]

        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            e = task.exception()
            if e:
                raise e

    async def test_set_parent_odu_alloc(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                sess.switch_datastore("running")
                setup_interface_hierarchy(sess)
                setup_shelf_and_sys(sess)
                setup_eth_port_config(sess, 0, "piu1", "eth-1", "port1")

                # nw-odu
                setup_interface(
                    sess,
                    "odu-1.1",
                    "piu1",
                    type="org-openroadm-interfaces:otnOdu",
                    sup_intf="oduc-piu1",
                )

                # set parent odu allocation
                sess.switch_datastore("running")
                sess.set_item(
                    "/org-openroadm-device:org-openroadm-device/interface[name='odu-1.1']/org-openroadm-otn-odu-interfaces:odu/parent-odu-allocation/trib-port-number",
                    1,
                )
                sess.set_item(
                    "/org-openroadm-device:org-openroadm-device/interface[name='odu-1.1']/org-openroadm-otn-odu-interfaces:odu/parent-odu-allocation/opucn-trib-slots",
                    ["1.1", "1.2"],
                )
                sess.apply_changes()

                sess.switch_datastore("operational")
                [data] = self.server.get_operational_data(
                    "/org-openroadm-device:org-openroadm-device/interface[name='odu-1.1']/org-openroadm-otn-odu-interfaces:odu/parent-odu-allocation"
                )
                expected = {
                    "trib-port-number": 1,
                    "opucn-trib-slots": ["['1.1', '1.2']"],
                }
                self.assertDictEqual(expected, data)

        self.tasks.append(asyncio.to_thread(test))
        tasks = [
            t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
            for t in self.tasks
        ]

        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            e = task.exception()
            if e:
                raise e

    async def asyncTearDown(self):
        await self.server.stop()
        self.tasks = []
        self.conn.disconnect()
        for process, q in self.processes:
            q.put(True)
            process.join()


if __name__ == "__main__":
    unittest.main()
