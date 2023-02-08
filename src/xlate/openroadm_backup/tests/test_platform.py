import asyncio
import itertools
import logging
import os
import time
import unittest
from multiprocessing import Process, Queue

import libyang
import sysrepo
# from goldstone.lib.core import *
from goldstone.xlate.openroadm.device import DeviceServer
from goldstone.xlate.openroadm.main import load_operational_modes
from goldstone.lib.core import ServerBase, ChangeHandler, NoOp
from goldstone.lib.connector.sysrepo import Connector
from goldstone.lib.errors import *
from .lib import *


class TestPlatformServer(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        logging.basicConfig(level=logging.DEBUG)
        self.conn = Connector()

        self.conn.delete_all("goldstone-platform")
        self.conn.delete_all("org-openroadm-device")
        self.conn.apply()
        # with self.conn.start_session() as sess:
        #     sess.switch_datastore("running")
        #     sess.replace_config({}, "goldstone-platform")
        #     sess.replace_config({}, "org-openroadm-device")
        #     sess.apply_changes()

        self.server = DeviceServer(
            self.conn,
            load_operational_modes(OPERATIONAL_MODES_PATH),
            reconciliation_interval=1,
        )
        self.q = Queue()
        self.process = Process(target=run_mock_gs_platformserver, args=(self.q,))
        self.process.start()

        servers = [self.server]

        self.tasks = list(
            itertools.chain.from_iterable([await s.start() for s in servers])
        )

    async def test_get_mock(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                sess.switch_datastore("operational")

                # ensure goldstone-platform is mocked by MockGSPlatformServer
                data = sess.get_data("/goldstone-platform:components")
                data = libyang.xpath_get(
                    data,
                    "/goldstone-platform:components/component[name='SYS']/sys/state/onie-info/vendor",
                )
                self.assertEqual(data, "test_vendor")

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

    async def test_get_info_vendor(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                sess.switch_datastore("operational")
                data = sess.get_data("/org-openroadm-device:org-openroadm-device")
                data = libyang.xpath_get(
                    data, "/org-openroadm-device:org-openroadm-device/info/vendor"
                )
                self.assertEqual(data, "test_vendor")

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

    async def test_get_info_model(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                sess.switch_datastore("operational")
                data = sess.get_data("/org-openroadm-device:org-openroadm-device")
                data = libyang.xpath_get(
                    data, "/org-openroadm-device:org-openroadm-device/info/model"
                )
                self.assertEqual(data, "test_part-number")

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

    async def test_get_info_serial_id(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                sess.switch_datastore("operational")
                data = sess.get_data("/org-openroadm-device:org-openroadm-device")
                data = libyang.xpath_get(
                    data, "/org-openroadm-device:org-openroadm-device/info/serial-id"
                )
                self.assertEqual(data, "test_serial-number")

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

    async def test_get_info_openroadmversion(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                sess.switch_datastore("operational")
                data = sess.get_data("/org-openroadm-device:org-openroadm-device")
                data = libyang.xpath_get(
                    data,
                    "/org-openroadm-device:org-openroadm-device/info/openroadm-version",
                )
                self.assertEqual(data, "10.0")

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

    async def test_get_circuit_pack_psu(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                sess.switch_datastore("operational")
                rdata = sess.get_data("/org-openroadm-device:org-openroadm-device")

                # Check PSU1 responses
                data = libyang.xpath_get(
                    rdata,
                    "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='PSU1']/model",
                )
                self.assertEqual(data, "PSU1_test_model")
                data = libyang.xpath_get(
                    rdata,
                    "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='PSU1']/serial-id",
                )
                self.assertEqual(data, "PSU1_test_serial")

                # Check PSU2 responses
                data = libyang.xpath_get(
                    rdata,
                    "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='PSU2']/model",
                )
                self.assertEqual(data, "PSU2_test_model")
                data = libyang.xpath_get(
                    rdata,
                    "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='PSU2']/serial-id",
                )
                self.assertEqual(data, "PSU2_test_serial")

                # Check PSU3 responses
                data = libyang.xpath_get(
                    rdata,
                    "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='PSU3']/serial-id",
                )
                self.assertEqual(data, "")

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

    async def test_get_transceiver(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                sess.switch_datastore("operational")
                data = sess.get_data("/org-openroadm-device:org-openroadm-device")

                # port1 transceiver (PRESENT)
                port1_data = libyang.xpath_get(
                    data,
                    "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']",
                )
                port1_expected = {
                    "circuit-pack-name": "port1",
                    "vendor": "transceiver_test_vendor_1",
                    "model": "transceiver_test_model_1",
                    "serial-id": "transceiver_test_serial_1",
                    "operational-state": "inService",
                    "is-pluggable-optics": True,
                    "is-physical": True,
                    "is-passive": False,
                    "faceplate-label": "none",
                }
                self.assertDictEqual(port1_data, port1_expected)

                # port2 transceiver (UNPLUGGED)
                port2_data = libyang.xpath_get(
                    data,
                    "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port2']",
                )
                port2_expected = {
                    "circuit-pack-name": "port2",
                    "vendor": "",
                    "model": "",
                    "serial-id": "",
                    "operational-state": "outOfService",
                    "is-pluggable-optics": True,
                    "is-physical": True,
                    "is-passive": False,
                    "faceplate-label": "none",
                }
                self.assertDictEqual(port2_data, port2_expected)

                # port16 transceiver (MISSING VENDOR)
                port16_data = libyang.xpath_get(
                    data,
                    "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port16']",
                )
                port16_expected = {
                    "circuit-pack-name": "port16",
                    "vendor": "",
                    "model": "transceiver_test_model_16",
                    "serial-id": "transceiver_test_serial_16",
                    "operational-state": "inService",
                    "is-pluggable-optics": True,
                    "is-physical": True,
                    "is-passive": False,
                    "faceplate-label": "none",
                }
                self.assertDictEqual(port16_data, port16_expected)

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

    async def test_get_base_circuit_pack(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                sess.switch_datastore("operational")
                data = sess.get_data("/org-openroadm-device:org-openroadm-device")

                base_data = libyang.xpath_get(
                    data,
                    "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='SYS']",
                )
                base_expected = {
                    "circuit-pack-name": "SYS",
                    "vendor": "test_vendor",
                    "model": "test_part-number",
                    "serial-id": "test_serial-number",
                    "operational-state": "inService",
                    "is-pluggable-optics": False,
                    "is-physical": True,
                    "is-passive": False,
                    "faceplate-label": "none",
                }
                self.assertDictEqual(base_data, base_expected)

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

    async def test_set_info(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:

                # test node-id success
                sess.switch_datastore("running")
                sess.set_item(
                    "/org-openroadm-device:org-openroadm-device/info/node-id", "a123456"
                )
                sess.apply_changes()

                data = sess.get_data("/org-openroadm-device:org-openroadm-device")
                data = libyang.xpath_get(
                    data, "/org-openroadm-device:org-openroadm-device/info/node-id"
                )
                self.assertEqual(data, "a123456")

                sess.switch_datastore("operational")
                data = sess.get_data("/org-openroadm-device:org-openroadm-device")
                data = libyang.xpath_get(
                    data, "/org-openroadm-device:org-openroadm-device/info/node-id"
                )
                self.assertEqual(data, "a123456")

                # test node-id fail
                sess.switch_datastore("running")
                self.assertRaises(
                    sysrepo.errors.SysrepoInvalArgError,
                    sess.set_item,
                    "/org-openroadm-device:org-openroadm-device/info/node-id",
                    "1",
                )

                # test node-number
                sess.switch_datastore("running")
                sess.set_item(
                    "/org-openroadm-device:org-openroadm-device/info/node-number", 1
                )
                sess.apply_changes()

                data = sess.get_data("/org-openroadm-device:org-openroadm-device")
                data = libyang.xpath_get(
                    data, "/org-openroadm-device:org-openroadm-device/info/node-number"
                )
                self.assertEqual(data, 1)

                sess.switch_datastore("operational")
                data = sess.get_data("/org-openroadm-device:org-openroadm-device")
                data = libyang.xpath_get(
                    data, "/org-openroadm-device:org-openroadm-device/info/node-number"
                )
                self.assertEqual(data, 1)

                # test node-type
                sess.switch_datastore("running")
                sess.set_item(
                    "/org-openroadm-device:org-openroadm-device/info/node-type", "xpdr"
                )
                sess.apply_changes()

                data = sess.get_data("/org-openroadm-device:org-openroadm-device")
                data = libyang.xpath_get(
                    data, "/org-openroadm-device:org-openroadm-device/info/node-type"
                )
                self.assertEqual(data, "xpdr")

                sess.switch_datastore("operational")
                data = sess.get_data("/org-openroadm-device:org-openroadm-device")
                data = libyang.xpath_get(
                    data, "/org-openroadm-device:org-openroadm-device/info/node-type"
                )
                self.assertEqual(data, "xpdr")

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

    async def test_create_shelf(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                # find sys component name
                sess.switch_datastore("operational")
                data = sess.get_data("/goldstone-platform:components/component")
                data = libyang.xpath_get(
                    data, "/goldstone-platform:components/component"
                )
                sys_comp_name = next(
                    (
                        comp.get("name")
                        for comp in data
                        if comp.get("state", {}).get("type") == "SYS"
                    ),
                    None,
                )

                # test provisioning of SYS shelf
                sess.switch_datastore("running")
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/shelf-name",
                    sys_comp_name,
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/shelf-type",
                    "SYS",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/administrative-state",
                    "inService",
                )
                sess.apply_changes()

                sess.switch_datastore("operational")
                data = sess.get_data("/org-openroadm-device:org-openroadm-device")
                data = libyang.xpath_get(
                    data,
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']",
                )
                expected = {
                    # user provisioned data
                    "shelf-name": sys_comp_name,
                    "shelf-type": "SYS",
                    "administrative-state": "inService",
                    "operational-state": "inService",
                    # static read only data
                    "vendor": "test_vendor",
                    "model": "test_part-number",
                    "serial-id": "test_serial-number",
                    "is-physical": True,
                    "is-passive": False,
                    "faceplate-label": "none",
                }
                self.assertDictEqual(data, expected)

                # test failure of arbitrary shelf creation
                sess.switch_datastore("running")
                sess.set_item(
                    "/org-openroadm-device:org-openroadm-device/shelves[shelf-name='test_shelf']/shelf-name",
                    "test_shelf",
                )
                sess.set_item(
                    "/org-openroadm-device:org-openroadm-device/shelves[shelf-name='test_shelf']/shelf-type",
                    "SYS",
                )
                sess.set_item(
                    "/org-openroadm-device:org-openroadm-device/shelves[shelf-name='test_shelf']/administrative-state",
                    "inService",
                )

                self.assertRaises(
                    sysrepo.errors.SysrepoCallbackFailedError, sess.apply_changes
                )

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

    async def test_create_circuit_pack(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                # find sys component name
                sess.switch_datastore("operational")
                data = sess.get_data("/goldstone-platform:components/component")
                data = libyang.xpath_get(
                    data, "/goldstone-platform:components/component"
                )
                sys_comp_name = next(
                    (
                        comp.get("name")
                        for comp in data
                        if comp.get("state", {}).get("type") == "SYS"
                    ),
                    None,
                )

                # test provisioning of base circuit-pack
                sess.switch_datastore("running")

                # provisional required SYS shelf
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/shelf-name",
                    sys_comp_name,
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/shelf-type",
                    "SYS",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/administrative-state",
                    "inService",
                )
                sess.apply_changes()

                # provision base circuit-pack
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/circuit-pack-name",
                    sys_comp_name,
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/circuit-pack-type",
                    "test_type",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/administrative-state",
                    "inService",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/shelf",
                    sys_comp_name,
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/slot",
                    "test_slot",
                )
                sess.apply_changes()

                sess.switch_datastore("operational")
                data = sess.get_data("/org-openroadm-device:org-openroadm-device")
                data = libyang.xpath_get(
                    data,
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']",
                )
                expected = {
                    # user provisioned data
                    "circuit-pack-name": sys_comp_name,
                    "circuit-pack-type": "test_type",
                    "administrative-state": "inService",
                    "shelf": sys_comp_name,
                    "slot": "test_slot",
                    # static read only data
                    "operational-state": "inService",
                    "vendor": "test_vendor",
                    "model": "test_part-number",
                    "serial-id": "test_serial-number",
                    "is-pluggable-optics": False,
                    "is-physical": True,
                    "is-passive": False,
                    "faceplate-label": "none",
                }
                self.assertDictEqual(data, expected)

                # test failure of arbitary circuit-pack creation
                sess.switch_datastore("running")
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='test_pack']/circuit-pack-name",
                    "test_pack",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='test_pack']/circuit-pack-type",
                    "test_type",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='test_pack']/administrative-state",
                    "inService",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='test_pack']/shelf",
                    sys_comp_name,
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='test_pack']/slot",
                    "test_slot",
                )

                self.assertRaises(
                    sysrepo.errors.SysrepoCallbackFailedError, sess.apply_changes
                )

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

    async def test_create_circuit_pack_port(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                # find sys component name
                sess.switch_datastore("operational")
                data = sess.get_data("/goldstone-platform:components/component")
                data = libyang.xpath_get(
                    data, "/goldstone-platform:components/component"
                )
                sys_comp_name = next(
                    (
                        comp.get("name")
                        for comp in data
                        if comp.get("state", {}).get("type") == "SYS"
                    ),
                    None,
                )

                # test port provisioning
                sess.switch_datastore("running")

                # provisional required SYS shelf
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/shelf-name",
                    sys_comp_name,
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/shelf-type",
                    "SYS",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/administrative-state",
                    "inService",
                )
                sess.apply_changes()

                # provision port1 circuit-pack
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/circuit-pack-name",
                    sys_comp_name,
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/circuit-pack-type",
                    "test_type",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/administrative-state",
                    "inService",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/shelf",
                    sys_comp_name,
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/slot",
                    "test_slot",
                )
                sess.apply_changes()

                # provision port "1" for port1 circuit-pack
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/ports[port-name='1']/port-name",
                    "1",
                )
                sess.apply_changes()

                sess.switch_datastore("operational")
                data = sess.get_data("/org-openroadm-device:org-openroadm-device")
                data = libyang.xpath_get(
                    data,
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/ports[port-name='1']",
                )
                expected = {
                    # user provisioned data
                    "port-name": "1",
                    # static read only data
                    "port-direction": "bidirectional",
                    "is-physical": True,
                    "faceplate-label": "none",
                    "operational-state": "inService",
                }
                self.assertDictEqual(data, expected)

                # test failure of arbitary port-name creation
                sess.switch_datastore("running")
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/ports[port-name='test_port']/port-name",
                    "test_port",
                )
                self.assertRaises(
                    sysrepo.errors.SysrepoCallbackFailedError, sess.apply_changes
                )
                sess.discard_changes()

                # test failure of creation of port for non-PIU/TRANSCIEVER circuit-pack
                # provision base circuit-pack
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/circuit-pack-name",
                    sys_comp_name,
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/circuit-pack-type",
                    "test_type",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/administrative-state",
                    "inService",
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/shelf",
                    sys_comp_name,
                )
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/slot",
                    "test_slot",
                )
                sess.apply_changes()

                # test failure of provisioning port for base circuit-pack
                sess.set_item(
                    f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/ports[port-name='1']/port-name",
                    "1",
                )
                self.assertRaises(
                    sysrepo.errors.SysrepoCallbackFailedError, sess.apply_changes
                )
                sess.discard_changes()

                # Test deletion of circuit-packs
                sess.switch_datastore("running")

                # Get the existing circuit-packs in running datastore
                data = sess.get_data(
                    "/org-openroadm-device:org-openroadm-device/circuit-packs"
                )

                # Get the list of circuit-pack-name
                cp_name_list = libyang.xpath_get(
                    data,
                    "/org-openroadm-device:org-openroadm-device/circuit-packs/circuit-pack-name",
                )

                # delete the circuit-packs in running datastore
                for cp_name in cp_name_list:
                    sess.delete_item(
                        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{cp_name}']"
                    )
                    sess.apply_changes()

                # check running datastore that all circuit-packs are deleted
                data = sess.get_data("/org-openroadm-device:org-openroadm-device")
                data = libyang.xpath_get(
                    data, f"/org-openroadm-device:org-openroadm-device/circuit-packs"
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

    async def test_get_optical_operational_mode_profile(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                sess.switch_datastore("operational")
                data = sess.get_data("/org-openroadm-device:org-openroadm-device")
                profile_data = libyang.xpath_get(
                    data,
                    f"/org-openroadm-device:org-openroadm-device/optical-operational-mode-profile",
                )

            # check Open ROADM profile display with the profile list in JSON file
            for mode in self.server.operational_modes:
                my_profile_name = mode.get("openroadm", {}).get("profile-name")
                if my_profile_name != None:
                    self.assertIn(my_profile_name, profile_data)

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
        self.q.put(True)
        self.process.join()


if __name__ == "__main__":
    unittest.main()
