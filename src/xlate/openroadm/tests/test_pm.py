import asyncio
import itertools
import json
import logging
import os
import time
import unittest
from multiprocessing import Process, Queue

import libyang
import sysrepo
from goldstone.lib.core import *
from goldstone.xlate.openroadm.main import load_operational_modes
from goldstone.xlate.openroadm.pm import PMServer
from goldstone.xlate.openroadm.device import DeviceServer

from .lib import *


class TestPMServer(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        logging.basicConfig(level=logging.DEBUG)
        self.conn = sysrepo.SysrepoConnection()

        with self.conn.start_session() as sess:
            sess.switch_datastore("running")
            sess.replace_config({}, "goldstone-transponder")
            sess.replace_config({}, "goldstone-platform")
            sess.replace_config({}, "org-openroadm-device")
            sess.replace_config({}, "org-openroadm-pm")
            sess.apply_changes()

        self.server = PMServer(
            self.conn,
            reconciliation_interval=1,
        )
        device_server = DeviceServer(
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

        servers = [self.server, device_server]

        self.tasks = list(
            itertools.chain.from_iterable([await s.start() for s in servers])
        )

    async def test_get_optical_power_input(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                setup_interface_hierarchy(sess)
                sess.switch_datastore("operational")

                data = sess.get_data(
                    "/org-openroadm-pm:current-pm-list/current-pm-entry/current-pm[type='opticalPowerInput']"
                )
                expected = {
                    "current-pm-list": {
                        "current-pm-entry": [
                            {
                                "pm-resource-type": "port",
                                "pm-resource-type-extension": "",
                                "pm-resource-instance": "/org-openroadm-device:org-openroadm-device/circuit-packs[name='piu1']/ports[port-name='1']",
                                "current-pm": [
                                    {
                                        "type": "opticalPowerInput",
                                        "extension": "",
                                        "location": "nearEnd",
                                        "direction": "rx",
                                        "measurement": [
                                            {
                                                "granularity": "notApplicable",
                                                "pmParameterValue": 0.0,  # not able to test from sysrepo, doesn't interpret union type properly
                                            }
                                        ],
                                    }
                                ],
                            }
                        ]
                    }
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

    async def test_get_optical_power_output(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                setup_interface_hierarchy(sess)

                sess.switch_datastore("operational")
                data = sess.get_data(
                    "/org-openroadm-pm:current-pm-list/current-pm-entry/current-pm[type='opticalPowerOutput']"
                )
                expected = {
                    "current-pm-list": {
                        "current-pm-entry": [
                            {
                                "pm-resource-type": "port",
                                "pm-resource-type-extension": "",
                                "pm-resource-instance": "/org-openroadm-device:org-openroadm-device/circuit-packs[name='piu1']/ports[port-name='1']",
                                "current-pm": [
                                    {
                                        "type": "opticalPowerOutput",
                                        "extension": "",
                                        "location": "nearEnd",
                                        "direction": "tx",
                                        "measurement": [
                                            {
                                                "granularity": "notApplicable",
                                                "pmParameterValue": 0.0,  # not able to test from sysrepo, doesn't interpret union type properly
                                            }
                                        ],
                                    }
                                ],
                            }
                        ]
                    }
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

    async def test_get_prefec_ber(self):
        def test():
            time.sleep(2)  # wait for the mock server
            with self.conn.start_session() as sess:
                setup_interface_hierarchy(sess)

                sess.switch_datastore("operational")
                data = sess.get_data(
                    "/org-openroadm-pm:current-pm-list/current-pm-entry/current-pm[type='preFECbitErrorRate']"
                )
                expected = {
                    "current-pm-list": {
                        "current-pm-entry": [
                            {
                                "pm-resource-type": "interface",
                                "pm-resource-type-extension": "",
                                "pm-resource-instance": "/org-openroadm-device:org-openroadm-device/interface[name='otsi-piu1']",
                                "current-pm": [
                                    {
                                        "type": "preFECbitErrorRate",
                                        "extension": "",
                                        "location": "nearEnd",
                                        "direction": "rx",
                                        "measurement": [
                                            {
                                                "granularity": "notApplicable",
                                                "pmParameterValue": 0.0,  # not able to test from sysrepo, doesn't interpret union type properly
                                            }
                                        ],
                                    }
                                ],
                            }
                        ]
                    }
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
