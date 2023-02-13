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
operational_modes = load_operational_modes()

class TestPMServer(XlateTestCase):
    async def asyncSetUp(self):
        XLATE_SERVER_OPT = [operational_modes]
        XLATE_MODULES = ["org-openroadm-device", "org-openroadm-pm"]
        MOCK_MODULES = ["goldstone-platform", "goldstone-transponder"]
        
        # await super().asyncSetUp()
        # Cannot fetch MOCK_MODULES using super().asyncSetUp
        
        logging.basicConfig(level=logging.DEBUG)
        self.conn = Connector()

        for module in MOCK_MODULES:
            self.conn.delete_all(module)
        for module in XLATE_MODULES:
            self.conn.delete_all(module)
        self.conn.apply()

        self.q = Queue()
        self.process = Process(target=run_mock_server, args=(self.q, MOCK_MODULES))
        self.process.start()

        self.server = PMServer(
            self.conn, reconciliation_interval=1
        )
        device_server = DeviceServer(
            self.conn,
            operational_modes,
            reconciliation_interval=1,
        )
        servers = [self.server, device_server]

        tasks = [asyncio.create_task(c) for server in servers for c in await server.start()]
        self.tasks = list(tasks)


    async def test_get_optical_power_input(self):
        def test():
            time.sleep(2)  # wait for the mock server
            setup_interface_hierarchy(self.conn)

            data = self.conn.get_operational(
                "/org-openroadm-pm:current-pm-list/current-pm-entry/current-pm[type='opticalPowerInput']"
            )
            # pm_data = self.conn.get_operational(
            #     "/org-openroadm-pm:current-pm-list/current-pm-entry"
            # )
            # print("pm_data === ", data)
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

        await self.run_xlate_test(test)

    # async def test_get_optical_power_output(self):
    #     def test():
    #         time.sleep(2)  # wait for the mock server

    #         setup_interface_hierarchy(self.conn)

    #         data = self.conn.get_operational(
    #             "/org-openroadm-pm:current-pm-list/current-pm-entry/current-pm[type='opticalPowerOutput']"
    #         )
    #         expected = {
    #             "current-pm-list": {
    #                 "current-pm-entry": [
    #                     {
    #                         "pm-resource-type": "port",
    #                         "pm-resource-type-extension": "",
    #                         "pm-resource-instance": "/org-openroadm-device:org-openroadm-device/circuit-packs[name='piu1']/ports[port-name='1']",
    #                         "current-pm": [
    #                             {
    #                                 "type": "opticalPowerOutput",
    #                                 "extension": "",
    #                                 "location": "nearEnd",
    #                                 "direction": "tx",
    #                                 "measurement": [
    #                                     {
    #                                         "granularity": "notApplicable",
    #                                         "pmParameterValue": 0.0,  # not able to test from sysrepo, doesn't interpret union type properly
    #                                     }
    #                                 ],
    #                             }
    #                         ],
    #                     }
    #                 ]
    #             }
    #         }
    #         self.assertDictEqual(expected, data)

        # await self.run_xlate_test(test)

    # async def test_get_prefec_ber(self):
    #     def test():
    #         time.sleep(2)  # wait for the mock server
    #         # with self.conn.start_session() as sess:
    #         setup_interface_hierarchy(self.conn)

    #         data = self.conn.get_operational(
    #             "/org-openroadm-pm:current-pm-list/current-pm-entry/current-pm[type='preFECbitErrorRate']"
    #         )
    #         expected = {
    #             "current-pm-list": {
    #                 "current-pm-entry": [
    #                     {
    #                         "pm-resource-type": "interface",
    #                         "pm-resource-type-extension": "",
    #                         "pm-resource-instance": "/org-openroadm-device:org-openroadm-device/interface[name='otsi-piu1']",
    #                         "current-pm": [
    #                             {
    #                                 "type": "preFECbitErrorRate",
    #                                 "extension": "",
    #                                 "location": "nearEnd",
    #                                 "direction": "rx",
    #                                 "measurement": [
    #                                     {
    #                                         "granularity": "notApplicable",
    #                                         "pmParameterValue": 0.0,  # not able to test from sysrepo, doesn't interpret union type properly
    #                                     }
    #                                 ],
    #                             }
    #                         ],
    #                     }
    #                 ]
    #             }
    #         }
    #         self.assertDictEqual(expected, data)

        await self.run_xlate_test(test)

    async def asyncTearDown(self):
        await call(self.server.stop)
        self.tasks = [t.cancel() for t in self.tasks]
        self.conn.stop()
        self.q.put({"type": "stop"})
        self.process.join()
