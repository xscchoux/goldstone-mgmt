"""Library for tests for translator services."""


import unittest
import os
import json
import asyncio
import logging
import time
from multiprocessing import Process, Queue
from queue import Empty
from goldstone.lib.core import ServerBase, ChangeHandler, NoOp
from goldstone.lib.connector.sysrepo import Connector
from goldstone.lib.util import call
# import libyang
# import sysrepo
# from goldstone.lib.core import *

OPERATIONAL_MODES_PATH = (
    os.path.dirname(__file__) + "/../../../../scripts/operational-modes.json"
)

def load_operational_modes():
    try:
        with open(OPERATIONAL_MODES_PATH, "r") as f:
            return json.loads(f.read())
    except json.decoder.JSONDecodeError as e:
        logger.error("Invalid configuration file %s.", OPERATIONAL_MODES_PATH)
        raise e
    except FileNotFoundError as e:
        logger.error("Configuration file %s is not found.", OPERATIONAL_MODES_PATH)
        raise e

    # with open(
    #     os.path.dirname(__file__) + "/../../../../scripts/operational-modes.json", "r", encoding = "utf-8"
    # ) as f:
    #     modes = json.loads(f.read())
    #     parsed_modes = {}
    #     for mode in modes:
    #         try:
    #             parsed_modes[mode["openroadm"]["profile-name"]] = {
    #                 "description": mode["description"],
    #                 "line-rate": mode["line-rate"],
    #                 "modulation-format": mode["modulation-format"],
    #                 "fec-type": mode["fec-type"],
    #             }
    #         except (KeyError, TypeError):
    #             pass
    # return parsed_modes

class FailApplyChangeHandler(ChangeHandler):
    def apply(self, user):
        raise Exception("Failed to apply for testing.")


class MockGSServer(ServerBase):
    """MockGSServer is mock handler server for Goldstone primitive models.

    Attributes:
        oper_data (dict): Data for oper_cb() to return. You can set this to configure mock's behavior.
    """

    def __init__(self, conn, module):
        super().__init__(conn, module)
        self.oper_data = {}

    def oper_cb(self, xpath, priv):
        return self.oper_data


class MockGSInterfaceServer(MockGSServer):
    def __init__(self, conn):
        super().__init__(conn, "goldstone-interfaces")
        self.handlders = {
            "interfaces": {
                "interface": {
                    "name": NoOp,
                    "config": {
                        "admin-status": NoOp,
                        "name": NoOp,
                        "description": NoOp,
                        "interface-type": NoOp,
                        "loopback-mode": NoOp,
                        "prbs-mode": NoOp,
                    },
                    "ethernet": NoOp,
                    "switched-vlan": NoOp,
                    "component-connection": NoOp,
                }
            }
        }

class MockGSPlatformServer(MockGSServer):
    def __init__(self, conn):
        super().__init__(conn, "goldstone-platform")
        self.handlers = {
            "components": {
                "component": {
                    "name": NoOp,
                    "config": {
                        "name": NoOp,
                    }
                }
            }
        }

class MockGSTransponderServer(MockGSServer):
    def __init__(self, conn):
        super().__init__(conn, "goldstone-transponder")
        self.handlers = {
            "modules": {
                "module": {
                    "name": NoOp,
                    "config": {"name": NoOp, "admin-status": NoOp},
                    "network-interface": {
                        "name": NoOp,
                        "config": {
                            "name": NoOp,
                            "tx-dis": NoOp,
                            "tx-laser-freq": NoOp,
                            "output-power": NoOp,
                            "line-rate": NoOp,
                            "modulation-format": NoOp,
                            "fec-type": NoOp,
                            "client-signal-mapping-type": NoOp,
                        },
                    },
                }
            }
        }


class MockGSSystemServer(MockGSServer):
    def __init__(self, conn):
        super().__init__(conn, "goldstone-system")
        self.handlers = {}


class MockGSGearboxServer(MockGSServer):
    def __init__(self, conn):
        super().__init__(conn, "goldstone-gearbox")
        self.handlers = {}


MOCK_SERVERS = {
    # "goldstone-interfaces": MockGSInterfaceServer,
    "goldstone-platform": MockGSPlatformServer,
    "goldstone-transponder": MockGSTransponderServer,
    # "goldstone-system": MockGSSystemServer,
    # "goldstone-gearbox": MockGSGearboxServer,
}

mock_data_platform = {
    "components": {
        "component": [
            {
                "name": "SYS",
                "state": {
                    "type": "SYS",
                },
                "sys": {
                    "state": {
                        "onie-info": {
                            "vendor": "test_vendor",
                            "part-number": "test_part-number",
                            "serial-number": "test_serial-number",
                        },
                    },
                },
            },
            {
                "name": "PSU1",
                "state": {
                    "type": "PSU",
                },
                "psu": {
                    "state": {
                        "model": "PSU1_test_model",
                        "serial": "PSU1_test_serial",
                    },
                },
            },
            {
                "name": "PSU2",
                "state": {
                    "type": "PSU",
                },
                "psu": {
                    "state": {
                        "model": "PSU2_test_model",
                        "serial": "PSU2_test_serial",
                    },
                },
            },
            # incomplete data
            {
                "name": "PSU3",
                "state": {
                    "type": "PSU",
                },
                "psu": {
                    "state": {
                        "serial": None,
                    },
                },
            },
            {
                "name": "port1",
                "state": {
                    "type": "TRANSCEIVER",
                },
                "transceiver": {
                    "state": {
                        "presence": "PRESENT",
                        "model": "transceiver_test_model_1",
                        "serial": "transceiver_test_serial_1",
                        "vendor": "transceiver_test_vendor_1",
                    },
                },
            },
            {
                "name": "port2",
                "state": {
                    "type": "TRANSCEIVER",
                },
                "transceiver": {
                    "state": {
                        "presence": "UNPLUGGED",
                    },
                },
            },
            {
                "name": "port5",
                "state": {
                    "type": "TRANSCEIVER",
                },
                "transceiver": {
                    "state": {
                        "presence": "PRESENT",
                        "model": "transceiver_test_model_5",
                        "serial": "transceiver_test_serial_5",
                    },
                },
            },
            {
                "name": "port9",
                "state": {
                    "type": "TRANSCEIVER",
                },
                "transceiver": {
                    "state": {
                        "presence": "PRESENT",
                        "model": "transceiver_test_model_9",
                        "serial": "transceiver_test_serial_9",
                    },
                },
            },
            {
                "name": "port13",
                "state": {
                    "type": "TRANSCEIVER",
                },
                "transceiver": {
                    "state": {
                        "presence": "PRESENT",
                        "model": "transceiver_test_model_13",
                        "serial": "transceiver_test_serial_13",
                    },
                },
            },
            {
                "name": "port16",
                "state": {
                    "type": "TRANSCEIVER",
                },
                "transceiver": {
                    "state": {
                        "presence": "PRESENT",
                        "model": "transceiver_test_model_16",
                        "serial": "transceiver_test_serial_16",
                    },
                },
            },
            {
                "name": "piu1",
                "state": {
                    "type": "PIU",
                },
            },
            {
                "name": "piu2",
                "state": {
                    "type": "PIU",
                },
            },
            {
                "name": "piu3",
                "state": {
                    "type": "PIU",
                },
            },
            {
                "name": "piu4",
                "state": {
                    "type": "PIU",
                },
            },
        ]
    }
}

mock_data_transponder = {
    "modules" :{
        "module": [
            {
                "name": "piu1",
                "state": {
                    "vendor-name": "piu1_vendor_name",
                    "vendor-part-number": "piu1_vendor_pn",
                    "vendor-serial-number": "piu1_vendor_sn",
                    "oper-status": "ready",
                },
                "network-interface": [
                    {
                        "name": "0",
                        "config": {
                            "name": "0",
                            "output-power": -123.456789,
                        },
                        "state": {
                            "current-output-power": -20.1,
                            "current-input-power": 70.0,
                            "current-post-voa-total-power": 12,
                            "current-pre-fec-ber": "OiIFOA==",
                        },
                    },
                ],
                "host-interface": [
                    {
                        "name": "0",
                        "config": {
                            "name": "0",
                            "signal-rate": "100-gbe",
                            "fec-type": "rs",
                            "loopback-type": "shallow",
                        },
                        "state": {
                            "signal-rate": "100-gbe",
                        },
                    },
                ],
            },
            {
                "name": "piu2",
                "state": {
                    "vendor-name": "piu2_vendor_name",
                    "oper-status": "unknown",
                },
                "network-interface": [
                    {
                        "name": "0",
                        "config": {
                            "name": "0",
                            "output-power": 23.4567,
                        },
                    },
                ],
                "host-interface": [
                    {
                        "name": "0",
                        "config": {
                            "name": "0",
                            "signal-rate": "200-gbe",
                            "fec-type": "fc",
                            "loopback-type": "shallow",
                        },
                        "state": {
                            "signal-rate": "200-gbe",
                        },
                    },
                    {
                        "name": "1",
                        "config": {
                            "name": "1",
                            "signal-rate": "200-gbe",
                            "fec-type": "fc",
                            "loopback-type": "shallow",
                        },
                        "state": {
                            "signal-rate": "200-gbe",
                        },
                    },
                ],
            },
            {
                "name": "piu3",
                "state": {
                    "vendor-name": "piu3_vendor_name",
                    "vendor-serial-number": "piu3_vendor_sn",
                    "oper-status": "initialize",
                },
                "network-interface": [
                    {
                        "name": "0",
                        "config": {
                            "name": "0",
                            "output-power": 0,
                        },
                    },
                ],
                "host-interface": [
                    {
                        "name": "0",
                        "config": {
                            "name": "0",
                            "signal-rate": "400-gbe",
                            "fec-type": "none",
                            "loopback-type": "none",
                        },
                        "state": {
                            "signal-rate": "400-gbe",
                        },
                    },
                    {
                        "name": "1",
                        "config": {
                            "name": "1",
                            "signal-rate": "400-gbe",
                            "fec-type": "none",
                            "loopback-type": "none",
                        },
                        "state": {
                            "signal-rate": "400-gbe",
                        },
                    },
                    {
                        "name": "2",
                        "config": {
                            "name": "2",
                            "signal-rate": "400-gbe",
                            "fec-type": "none",
                            "loopback-type": "none",
                        },
                        "state": {
                            "signal-rate": "400-gbe",
                        },
                    },
                    {
                        "name": "3",
                        "config": {
                            "name": "3",
                            "signal-rate": "400-gbe",
                            "fec-type": "none",
                            "loopback-type": "none",
                        },
                        "state": {
                            "signal-rate": "400-gbe",
                        },
                    },
                ],
            },
            {
                "name": "piu4",
                "state": {
                    "vendor-part-number": "piu4_vendor_pn",
                    "oper-status": "unknown",
                },
                "network-interface": [
                    {
                        # no power on this interface
                        "name": "0",
                        "config": {
                            "name": "0",
                        },
                    },
                ],
                "host-interface": [
                    {
                        "name": "0",
                        "config": {
                            "name": "0",
                            "signal-rate": "otu4",
                            "fec-type": "rs",
                            "loopback-type": "shallow",
                        },
                        "state": {
                            "signal-rate": "otu4",
                        },
                    },
                    {
                        "name": "1",
                        "config": {
                            "name": "1",
                            "signal-rate": "otu4",
                            "fec-type": "rs",
                            "loopback-type": "shallow",
                        },
                        "state": {
                            "signal-rate": "otu4",
                        },
                    },
                    {
                        "name": "2",
                        "config": {
                            "name": "1",
                            "signal-rate": "otu4",
                            "fec-type": "rs",
                            "loopback-type": "shallow",
                        },
                        "state": {
                            "signal-rate": "otu4",
                        },
                    },
                    {
                        "name": "3",
                        "config": {
                            "name": "1",
                            "signal-rate": "otu4",
                            "fec-type": "rs",
                            "loopback-type": "shallow",
                        },
                        "state": {
                            "signal-rate": "otu4",
                        },
                    },
                ],
            },
        ]
    }
}

MOCK_OPER_DATA = {
    "goldstone-platform": mock_data_platform,
    "goldstone-transponder":mock_data_transponder,
}


def run_mock_server(q, mock_modules):
    """Run mock servers.

    A TestCase can communicate with MockServers by using a Queue.
        Stop MockServers: {"type": "stop"}
        Set operational state data of a MockServer: {"type": "set", "server": "<SERVER_NAME>", "data": "<DATA_TO_SET>"}

    Args:
        q (Queue): Queue to communicate between a TestCase and MockServers.
        mock_modules (list of str): Names of modules to mock. Keys in MOCK_SERVERS
    """
    conn = Connector()
    servers = {}
    for mock_module in mock_modules:
        servers[mock_module] = MOCK_SERVERS[mock_module](conn)

    async def _main():
        tasks = []
        for server in servers.items():
            tasks += await server[1].start()
        
        async def evloop():
            while True:
                await asyncio.sleep(0.01)
                try:
                    msg = q.get(block=False)
                except Empty:
                    pass
                else:
                    if msg["type"] == "stop":
                        return
                    elif msg["type"] == "set-oper-data":
                        servers[msg["server"]].oper_data = msg["data"]
                    elif msg["type"] == "set-change-handler":
                        handler = servers[msg["server"]].handlers
                        nodes = msg["path"].split("/")[1:]
                        for i, node in enumerate(nodes):
                            if i >= len(nodes) - 1:
                                handler[node] = msg["handler"]
                            else:
                                handler = handler[node]
        tasks.append(evloop())
        tasks = [
            t if isinstance(t, asyncio.Task) else asyncio.create_task(t) for t in tasks
        ]

        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            e = task.exception()
            if e:
                raise e

    asyncio.run(_main())
    conn.stop()


class XlateTestCase(unittest.IsolatedAsyncioTestCase):
    """Test case base class for translator servers.

    Attributes:
        XLATE_SERVER (ServerBase): Server class to test.
        XLATE_SERVER_OPT (list): Arguments that will be given to the server.
        XLATE_MODULES (list): Module names the server will provide.
        MOCK_MODULES (list): Module names the server will use.
    """

    async def asyncSetUp(self):
        logging.basicConfig(level=logging.DEBUG)
        self.conn = Connector()

        for module in self.MOCK_MODULES:
            self.conn.delete_all(module)
        for module in self.XLATE_MODULES:
            self.conn.delete_all(module)
        self.conn.apply()

        self.q = Queue()
        self.process = Process(target=run_mock_server, args=(self.q, self.MOCK_MODULES))
        self.process.start()

        self.server = self.XLATE_SERVER(
            self.conn, reconciliation_interval=1, *self.XLATE_SERVER_OPT
        )
        self.tasks = list(asyncio.create_task(c) for c in await self.server.start())

        for module in self.MOCK_MODULES:
            self.set_mock_oper_data(module, MOCK_OPER_DATA[module])

    async def run_xlate_test(self, test):
        """Run a test as a thread.

        Args:
            test (func): Test to run.
        """
        time.sleep(1) #wait for the mock server
        await asyncio.create_task(asyncio.to_thread(test))

    def set_mock_oper_data(self, server, data):
        """Set operational state data to the mock server.
        Args:
            server (str): Target mock server name. A key in MOCK_SERVERS.
            data (dict): Operational state data that the server returns.
        """
        self.q.put({"type": "set-oper-data", "server": server, "data": data})

    def set_mock_change_handler(self, server, path, handler):
        """Set ChangeHandler to the mock server.
        Args:
            server (str): Target mock server name. A key in MOCK_SERVERS.
            path (str): Path to node that the ChangeHandler handles.
            handler (ChangeHandler): ChangeHandler to set.
        """
        self.q.put(
            {
                "type": "set-change-handler",
                "server": server,
                "path": path,
                "handler": handler,
            }
        )

    async def asyncTearDown(self):
        await call(self.server.stop)
        self.tasks = [t.cancel() for t in self.tasks]
        self.conn.stop()
        self.q.put({"type": "stop"})
        self.process.join()

# class MockGSPlatformServer(ServerBase):
#     def __init__(self, conn):
#         super().__init__(conn, "goldstone-platform")
#         self.handlers = {}

#     def oper_cb(self, xpath, priv):
#         # mock goldstone-platform data here
#         components = [
#             {
#                 "name": "SYS",
#                 "state": {
#                     "type": "SYS",
#                 },
#                 "sys": {
#                     "state": {
#                         "onie-info": {
#                             "vendor": "test_vendor",
#                             "part-number": "test_part-number",
#                             "serial-number": "test_serial-number",
#                         },
#                     },
#                 },
#             },
#             {
#                 "name": "PSU1",
#                 "state": {
#                     "type": "PSU",
#                 },
#                 "psu": {
#                     "state": {
#                         "model": "PSU1_test_model",
#                         "serial": "PSU1_test_serial",
#                     },
#                 },
#             },
#             {
#                 "name": "PSU2",
#                 "state": {
#                     "type": "PSU",
#                 },
#                 "psu": {
#                     "state": {
#                         "model": "PSU2_test_model",
#                         "serial": "PSU2_test_serial",
#                     },
#                 },
#             },
#             # incomplete data
#             {
#                 "name": "PSU3",
#                 "state": {
#                     "type": "PSU",
#                 },
#                 "psu": {
#                     "state": {
#                         "serial": None,
#                     },
#                 },
#             },
#             {
#                 "name": "port1",
#                 "state": {
#                     "type": "TRANSCEIVER",
#                 },
#                 "transceiver": {
#                     "state": {
#                         "presence": "PRESENT",
#                         "model": "transceiver_test_model_1",
#                         "serial": "transceiver_test_serial_1",
#                         "vendor": "transceiver_test_vendor_1",
#                     },
#                 },
#             },
#             {
#                 "name": "port2",
#                 "state": {
#                     "type": "TRANSCEIVER",
#                 },
#                 "transceiver": {
#                     "state": {
#                         "presence": "UNPLUGGED",
#                     },
#                 },
#             },
#             {
#                 "name": "port5",
#                 "state": {
#                     "type": "TRANSCEIVER",
#                 },
#                 "transceiver": {
#                     "state": {
#                         "presence": "PRESENT",
#                         "model": "transceiver_test_model_5",
#                         "serial": "transceiver_test_serial_5",
#                     },
#                 },
#             },
#             {
#                 "name": "port9",
#                 "state": {
#                     "type": "TRANSCEIVER",
#                 },
#                 "transceiver": {
#                     "state": {
#                         "presence": "PRESENT",
#                         "model": "transceiver_test_model_9",
#                         "serial": "transceiver_test_serial_9",
#                     },
#                 },
#             },
#             {
#                 "name": "port13",
#                 "state": {
#                     "type": "TRANSCEIVER",
#                 },
#                 "transceiver": {
#                     "state": {
#                         "presence": "PRESENT",
#                         "model": "transceiver_test_model_13",
#                         "serial": "transceiver_test_serial_13",
#                     },
#                 },
#             },
#             {
#                 "name": "port16",
#                 "state": {
#                     "type": "TRANSCEIVER",
#                 },
#                 "transceiver": {
#                     "state": {
#                         "presence": "PRESENT",
#                         "model": "transceiver_test_model_16",
#                         "serial": "transceiver_test_serial_16",
#                     },
#                 },
#             },
#             {
#                 "name": "piu1",
#                 "state": {
#                     "type": "PIU",
#                 },
#             },
#             {
#                 "name": "piu2",
#                 "state": {
#                     "type": "PIU",
#                 },
#             },
#             {
#                 "name": "piu3",
#                 "state": {
#                     "type": "PIU",
#                 },
#             },
#             {
#                 "name": "piu4",
#                 "state": {
#                     "type": "PIU",
#                 },
#             },
#         ]
#         return {"components": {"component": components}}


# def run_mock_gs_platformserver(q):
#     conn = sysrepo.SysrepoConnection()
#     server = MockGSPlatformServer(conn)

#     async def _main():
#         tasks = await server.start()

#         async def evloop():
#             while True:
#                 await asyncio.sleep(1)
#                 try:
#                     q.get(False)
#                 except:
#                     pass
#                 else:
#                     return

#         tasks.append(evloop())
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t) for t in tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     asyncio.run(_main())


# class MockGSTransponderServer(ServerBase):
#     def __init__(self, conn):
#         super().__init__(conn, "goldstone-transponder")
#         self.handlers = {
#             "modules": {
#                 "module": {
#                     "name": NoOp,
#                     "config": {
#                         "name": NoOp,
#                     },
#                     "network-interface": {
#                         "name": NoOp,
#                         "config": {
#                             "name": NoOp,
#                             "output-power": NoOp,
#                             "line-rate": NoOp,
#                             "modulation-format": NoOp,
#                             "fec-type": NoOp,
#                             "tx-laser-freq": NoOp,
#                             "loopback-type": NoOp,
#                         },
#                     },
#                     "host-interface": {
#                         "name": NoOp,
#                         "config": {
#                             "name": NoOp,
#                             "signal-rate": NoOp,
#                             "fec-type": NoOp,
#                         },
#                     },
#                 }
#             }
#         }

#     def oper_cb(self, xpath, priv):
#         # mock goldstone-transponder data here
#         modules = [
#             {
#                 "name": "piu1",
#                 "state": {
#                     "vendor-name": "piu1_vendor_name",
#                     "vendor-part-number": "piu1_vendor_pn",
#                     "vendor-serial-number": "piu1_vendor_sn",
#                     "oper-status": "ready",
#                 },
#                 "network-interface": [
#                     {
#                         "name": "0",
#                         "config": {
#                             "name": "0",
#                             "output-power": -123.456789,
#                         },
#                         "state": {
#                             "current-output-power": -20.1,
#                             "current-input-power": 70.0,
#                             "current-post-voa-total-power": 12,
#                             "current-pre-fec-ber": "OiIFOA==",
#                         },
#                     },
#                 ],
#                 "host-interface": [
#                     {
#                         "name": "0",
#                         "config": {
#                             "name": "0",
#                             "signal-rate": "100-gbe",
#                             "fec-type": "rs",
#                             "loopback-type": "shallow",
#                         },
#                         "state": {
#                             "signal-rate": "100-gbe",
#                         },
#                     },
#                 ],
#             },
#             {
#                 "name": "piu2",
#                 "state": {
#                     "vendor-name": "piu2_vendor_name",
#                     "oper-status": "unknown",
#                 },
#                 "network-interface": [
#                     {
#                         "name": "0",
#                         "config": {
#                             "name": "0",
#                             "output-power": 23.4567,
#                         },
#                     },
#                 ],
#                 "host-interface": [
#                     {
#                         "name": "0",
#                         "config": {
#                             "name": "0",
#                             "signal-rate": "200-gbe",
#                             "fec-type": "fc",
#                             "loopback-type": "shallow",
#                         },
#                         "state": {
#                             "signal-rate": "200-gbe",
#                         },
#                     },
#                     {
#                         "name": "1",
#                         "config": {
#                             "name": "1",
#                             "signal-rate": "200-gbe",
#                             "fec-type": "fc",
#                             "loopback-type": "shallow",
#                         },
#                         "state": {
#                             "signal-rate": "200-gbe",
#                         },
#                     },
#                 ],
#             },
#             {
#                 "name": "piu3",
#                 "state": {
#                     "vendor-name": "piu3_vendor_name",
#                     "vendor-serial-number": "piu3_vendor_sn",
#                     "oper-status": "initialize",
#                 },
#                 "network-interface": [
#                     {
#                         "name": "0",
#                         "config": {
#                             "name": "0",
#                             "output-power": 0,
#                         },
#                     },
#                 ],
#                 "host-interface": [
#                     {
#                         "name": "0",
#                         "config": {
#                             "name": "0",
#                             "signal-rate": "400-gbe",
#                             "fec-type": "none",
#                             "loopback-type": "none",
#                         },
#                         "state": {
#                             "signal-rate": "400-gbe",
#                         },
#                     },
#                     {
#                         "name": "1",
#                         "config": {
#                             "name": "1",
#                             "signal-rate": "400-gbe",
#                             "fec-type": "none",
#                             "loopback-type": "none",
#                         },
#                         "state": {
#                             "signal-rate": "400-gbe",
#                         },
#                     },
#                     {
#                         "name": "2",
#                         "config": {
#                             "name": "2",
#                             "signal-rate": "400-gbe",
#                             "fec-type": "none",
#                             "loopback-type": "none",
#                         },
#                         "state": {
#                             "signal-rate": "400-gbe",
#                         },
#                     },
#                     {
#                         "name": "3",
#                         "config": {
#                             "name": "3",
#                             "signal-rate": "400-gbe",
#                             "fec-type": "none",
#                             "loopback-type": "none",
#                         },
#                         "state": {
#                             "signal-rate": "400-gbe",
#                         },
#                     },
#                 ],
#             },
#             {
#                 "name": "piu4",
#                 "state": {
#                     "vendor-part-number": "piu4_vendor_pn",
#                     "oper-status": "unknown",
#                 },
#                 "network-interface": [
#                     {
#                         # no power on this interface
#                         "name": "0",
#                         "config": {
#                             "name": "0",
#                         },
#                     },
#                 ],
#                 "host-interface": [
#                     {
#                         "name": "0",
#                         "config": {
#                             "name": "0",
#                             "signal-rate": "otu4",
#                             "fec-type": "rs",
#                             "loopback-type": "shallow",
#                         },
#                         "state": {
#                             "signal-rate": "otu4",
#                         },
#                     },
#                     {
#                         "name": "1",
#                         "config": {
#                             "name": "1",
#                             "signal-rate": "otu4",
#                             "fec-type": "rs",
#                             "loopback-type": "shallow",
#                         },
#                         "state": {
#                             "signal-rate": "otu4",
#                         },
#                     },
#                     {
#                         "name": "2",
#                         "config": {
#                             "name": "1",
#                             "signal-rate": "otu4",
#                             "fec-type": "rs",
#                             "loopback-type": "shallow",
#                         },
#                         "state": {
#                             "signal-rate": "otu4",
#                         },
#                     },
#                     {
#                         "name": "3",
#                         "config": {
#                             "name": "1",
#                             "signal-rate": "otu4",
#                             "fec-type": "rs",
#                             "loopback-type": "shallow",
#                         },
#                         "state": {
#                             "signal-rate": "otu4",
#                         },
#                     },
#                 ],
#             },
#         ]
#         return {"modules": {"module": modules}}


# def run_mock_gs_transponderserver(q):
#     conn = sysrepo.SysrepoConnection()
#     server = MockGSTransponderServer(conn)

#     async def _main():
#         tasks = await server.start()

#         async def evloop():
#             while True:
#                 await asyncio.sleep(1)
#                 try:
#                     q.get(False)
#                 except:
#                     pass
#                 else:
#                     return

#         tasks.append(evloop())
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t) for t in tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     asyncio.run(_main())


# def setup_interface(
#     sess, if_name, cp_name, type="org-openroadm-interfaces:otsi", sup_intf=None
# ):
#     """Setup/provision required leaves for OpenROADM interface.

#     Args:
#         sess (SysrepoSession): Sysrepo session used to make changes.
#         ori (str): Name of the OpenROADM interface to provision (opaque outside of OpenROADM)
#         cp_name (str): Name of supporting-circuit-pack. Must already be provisioned.
#         sup_intf (str): Name of supporting interface. Must already be provisioned.
#     """
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/interface[name='{if_name}']/supporting-circuit-pack-name",
#         f"{cp_name}",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/interface[name='{if_name}']/type",
#         type,
#     )
#     sess.set_item(class TestPlatformServer(unittest.IsolatedAsyncioTestCase):
#     async def asyncSetUp(self):
#         logging.basicConfig(level=logging.DEBUG)
#         self.conn = Connector()

#         self.conn.delete_all("goldstone-platform")
#         self.conn.delete_all("org-openroadm-device")
#         self.conn.apply()
#         # with self.conn.start_session() as sess:
#         #     sess.switch_datastore("running")
#         #     sess.replace_config({}, "goldstone-platform")
#         #     sess.replace_config({}, "org-openroadm-device")
#         #     sess.apply_changes()

#         self.server = DeviceServer(
#             self.conn,
#             load_operational_modes(OPERATIONAL_MODES_PATH),
#             reconciliation_interval=1,
#         )
#         self.q = Queue()
#         self.process = Process(target=run_mock_gs_platformserver, args=(self.q,))
#         self.process.start()

#         servers = [self.server]

#         self.tasks = list(
#             itertools.chain.from_iterable([await s.start() for s in servers])
#         )

#     async def test_get_mock(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 sess.switch_datastore("operational")

#                 # ensure goldstone-platform is mocked by MockGSPlatformServer
#                 data = sess.get_data("/goldstone-platform:components")
#                 data = libyang.xpath_get(
#                     data,
#                     "/goldstone-platform:components/component[name='SYS']/sys/state/onie-info/vendor",
#                 )
#                 self.assertEqual(data, "test_vendor")

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_get_info_vendor(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data, "/org-openroadm-device:org-openroadm-device/info/vendor"
#                 )
#                 self.assertEqual(data, "test_vendor")

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_get_info_model(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data, "/org-openroadm-device:org-openroadm-device/info/model"
#                 )
#                 self.assertEqual(data, "test_part-number")

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_get_info_serial_id(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data, "/org-openroadm-device:org-openroadm-device/info/serial-id"
#                 )
#                 self.assertEqual(data, "test_serial-number")

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_get_info_openroadmversion(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data,
#                     "/org-openroadm-device:org-openroadm-device/info/openroadm-version",
#                 )
#                 self.assertEqual(data, "10.0")

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_get_circuit_pack_psu(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 sess.switch_datastore("operational")
#                 rdata = sess.get_data("/org-openroadm-device:org-openroadm-device")

#                 # Check PSU1 responses
#                 data = libyang.xpath_get(
#                     rdata,
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='PSU1']/model",
#                 )
#                 self.assertEqual(data, "PSU1_test_model")
#                 data = libyang.xpath_get(
#                     rdata,
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='PSU1']/serial-id",
#                 )
#                 self.assertEqual(data, "PSU1_test_serial")

#                 # Check PSU2 responses
#                 data = libyang.xpath_get(
#                     rdata,
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='PSU2']/model",
#                 )
#                 self.assertEqual(data, "PSU2_test_model")
#                 data = libyang.xpath_get(
#                     rdata,
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='PSU2']/serial-id",
#                 )
#                 self.assertEqual(data, "PSU2_test_serial")

#                 # Check PSU3 responses
#                 data = libyang.xpath_get(
#                     rdata,
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='PSU3']/serial-id",
#                 )
#                 self.assertEqual(data, "")

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_get_transceiver(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")

#                 # port1 transceiver (PRESENT)
#                 port1_data = libyang.xpath_get(
#                     data,
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']",
#                 )
#                 port1_expected = {
#                     "circuit-pack-name": "port1",
#                     "vendor": "transceiver_test_vendor_1",
#                     "model": "transceiver_test_model_1",
#                     "serial-id": "transceiver_test_serial_1",
#                     "operational-state": "inService",
#                     "is-pluggable-optics": True,
#                     "is-physical": True,
#                     "is-passive": False,
#                     "faceplate-label": "none",
#                 }
#                 self.assertDictEqual(port1_data, port1_expected)

#                 # port2 transceiver (UNPLUGGED)
#                 port2_data = libyang.xpath_get(
#                     data,
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port2']",
#                 )
#                 port2_expected = {
#                     "circuit-pack-name": "port2",
#                     "vendor": "",
#                     "model": "",
#                     "serial-id": "",
#                     "operational-state": "outOfService",
#                     "is-pluggable-optics": True,
#                     "is-physical": True,
#                     "is-passive": False,
#                     "faceplate-label": "none",
#                 }
#                 self.assertDictEqual(port2_data, port2_expected)

#                 # port16 transceiver (MISSING VENDOR)
#                 port16_data = libyang.xpath_get(
#                     data,
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port16']",
#                 )
#                 port16_expected = {
#                     "circuit-pack-name": "port16",
#                     "vendor": "",
#                     "model": "transceiver_test_model_16",
#                     "serial-id": "transceiver_test_serial_16",
#                     "operational-state": "inService",
#                     "is-pluggable-optics": True,
#                     "is-physical": True,
#                     "is-passive": False,
#                     "faceplate-label": "none",
#                 }
#                 self.assertDictEqual(port16_data, port16_expected)

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_get_base_circuit_pack(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")

#                 base_data = libyang.xpath_get(
#                     data,
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='SYS']",
#                 )
#                 base_expected = {
#                     "circuit-pack-name": "SYS",
#                     "vendor": "test_vendor",
#                     "model": "test_part-number",
#                     "serial-id": "test_serial-number",
#                     "operational-state": "inService",
#                     "is-pluggable-optics": False,
#                     "is-physical": True,
#                     "is-passive": False,
#                     "faceplate-label": "none",
#                 }
#                 self.assertDictEqual(base_data, base_expected)

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_set_info(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:

#                 # test node-id success
#                 sess.switch_datastore("running")
#                 sess.set_item(
#                     "/org-openroadm-device:org-openroadm-device/info/node-id", "a123456"
#                 )
#                 sess.apply_changes()

#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data, "/org-openroadm-device:org-openroadm-device/info/node-id"
#                 )
#                 self.assertEqual(data, "a123456")

#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data, "/org-openroadm-device:org-openroadm-device/info/node-id"
#                 )
#                 self.assertEqual(data, "a123456")

#                 # test node-id fail
#                 sess.switch_datastore("running")
#                 self.assertRaises(
#                     sysrepo.errors.SysrepoInvalArgError,
#                     sess.set_item,
#                     "/org-openroadm-device:org-openroadm-device/info/node-id",
#                     "1",
#                 )

#                 # test node-number
#                 sess.switch_datastore("running")
#                 sess.set_item(
#                     "/org-openroadm-device:org-openroadm-device/info/node-number", 1
#                 )
#                 sess.apply_changes()

#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data, "/org-openroadm-device:org-openroadm-device/info/node-number"
#                 )
#                 self.assertEqual(data, 1)

#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data, "/org-openroadm-device:org-openroadm-device/info/node-number"
#                 )
#                 self.assertEqual(data, 1)

#                 # test node-type
#                 sess.switch_datastore("running")
#                 sess.set_item(
#                     "/org-openroadm-device:org-openroadm-device/info/node-type", "xpdr"
#                 )
#                 sess.apply_changes()

#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data, "/org-openroadm-device:org-openroadm-device/info/node-type"
#                 )
#                 self.assertEqual(data, "xpdr")

#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data, "/org-openroadm-device:org-openroadm-device/info/node-type"
#                 )
#                 self.assertEqual(data, "xpdr")

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_create_shelf(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 # find sys component name
#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/goldstone-platform:components/component")
#                 data = libyang.xpath_get(
#                     data, "/goldstone-platform:components/component"
#                 )
#                 sys_comp_name = next(
#                     (
#                         comp.get("name")
#                         for comp in data
#                         if comp.get("state", {}).get("type") == "SYS"
#                     ),
#                     None,
#                 )

#                 # test provisioning of SYS shelf
#                 sess.switch_datastore("running")
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/shelf-name",
#                     sys_comp_name,
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/shelf-type",
#                     "SYS",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/administrative-state",
#                     "inService",
#                 )
#                 sess.apply_changes()

#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data,
#                     f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']",
#                 )
#                 expected = {
#                     # user provisioned data
#                     "shelf-name": sys_comp_name,
#                     "shelf-type": "SYS",
#                     "administrative-state": "inService",
#                     "operational-state": "inService",
#                     # static read only data
#                     "vendor": "test_vendor",
#                     "model": "test_part-number",
#                     "serial-id": "test_serial-number",
#                     "is-physical": True,
#                     "is-passive": False,
#                     "faceplate-label": "none",
#                 }
#                 self.assertDictEqual(data, expected)

#                 # test failure of arbitrary shelf creation
#                 sess.switch_datastore("running")
#                 sess.set_item(
#                     "/org-openroadm-device:org-openroadm-device/shelves[shelf-name='test_shelf']/shelf-name",
#                     "test_shelf",
#                 )
#                 sess.set_item(
#                     "/org-openroadm-device:org-openroadm-device/shelves[shelf-name='test_shelf']/shelf-type",
#                     "SYS",
#                 )
#                 sess.set_item(
#                     "/org-openroadm-device:org-openroadm-device/shelves[shelf-name='test_shelf']/administrative-state",
#                     "inService",
#                 )

#                 self.assertRaises(
#                     sysrepo.errors.SysrepoCallbackFailedError, sess.apply_changes
#                 )

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_create_circuit_pack(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 # find sys component name
#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/goldstoneclass TestPlatformServer(unittest.IsolatedAsyncioTestCase):
#     async def asyncSetUp(self):
#         logging.basicConfig(level=logging.DEBUG)
#         self.conn = Connector()

#         self.conn.delete_all("goldstone-platform")
#         self.conn.delete_all("org-openroadm-device")
#         self.conn.apply()
#         # with self.conn.start_session() as sess:
#         #     sess.switch_datastore("running")
#         #     sess.replace_config({}, "goldstone-platform")
#         #     sess.replace_config({}, "org-openroadm-device")
#         #     sess.apply_changes()

#         self.server = DeviceServer(
#             self.conn,
#             load_operational_modes(OPERATIONAL_MODES_PATH),
#             reconciliation_interval=1,
#         )
#         self.q = Queue()
#         self.process = Process(target=run_mock_gs_platformserver, args=(self.q,))
#         self.process.start()

#         servers = [self.server]

#         self.tasks = list(
#             itertools.chain.from_iterable([await s.start() for s in servers])
#         )

#     async def test_get_mock(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 sess.switch_datastore("operational")

#                 # ensure goldstone-platform is mocked by MockGSPlatformServer
#                 data = sess.get_data("/goldstone-platform:components")
#                 data = libyang.xpath_get(
#                     data,
#                     "/goldstone-platform:components/component[name='SYS']/sys/state/onie-info/vendor",
#                 )
#                 self.assertEqual(data, "test_vendor")

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_get_info_vendor(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data, "/org-openroadm-device:org-openroadm-device/info/vendor"
#                 )
#                 self.assertEqual(data, "test_vendor")

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_get_info_model(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data, "/org-openroadm-device:org-openroadm-device/info/model"
#                 )
#                 self.assertEqual(data, "test_part-number")

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_get_info_serial_id(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data, "/org-openroadm-device:org-openroadm-device/info/serial-id"
#                 )
#                 self.assertEqual(data, "test_serial-number")

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_get_info_openroadmversion(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data,
#                     "/org-openroadm-device:org-openroadm-device/info/openroadm-version",
#                 )
#                 self.assertEqual(data, "10.0")

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_get_circuit_pack_psu(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 sess.switch_datastore("operational")
#                 rdata = sess.get_data("/org-openroadm-device:org-openroadm-device")

#                 # Check PSU1 responses
#                 data = libyang.xpath_get(
#                     rdata,
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='PSU1']/model",
#                 )
#                 self.assertEqual(data, "PSU1_test_model")
#                 data = libyang.xpath_get(
#                     rdata,
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='PSU1']/serial-id",
#                 )
#                 self.assertEqual(data, "PSU1_test_serial")

#                 # Check PSU2 responses
#                 data = libyang.xpath_get(
#                     rdata,
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='PSU2']/model",
#                 )
#                 self.assertEqual(data, "PSU2_test_model")
#                 data = libyang.xpath_get(
#                     rdata,
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='PSU2']/serial-id",
#                 )
#                 self.assertEqual(data, "PSU2_test_serial")

#                 # Check PSU3 responses
#                 data = libyang.xpath_get(
#                     rdata,
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='PSU3']/serial-id",
#                 )
#                 self.assertEqual(data, "")

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_get_transceiver(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")

#                 # port1 transceiver (PRESENT)
#                 port1_data = libyang.xpath_get(
#                     data,
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']",
#                 )
#                 port1_expected = {
#                     "circuit-pack-name": "port1",
#                     "vendor": "transceiver_test_vendor_1",
#                     "model": "transceiver_test_model_1",
#                     "serial-id": "transceiver_test_serial_1",
#                     "operational-state": "inService",
#                     "is-pluggable-optics": True,
#                     "is-physical": True,
#                     "is-passive": False,
#                     "faceplate-label": "none",
#                 }
#                 self.assertDictEqual(port1_data, port1_expected)

#                 # port2 transceiver (UNPLUGGED)
#                 port2_data = libyang.xpath_get(
#                     data,
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port2']",
#                 )
#                 port2_expected = {
#                     "circuit-pack-name": "port2",
#                     "vendor": "",
#                     "model": "",
#                     "serial-id": "",
#                     "operational-state": "outOfService",
#                     "is-pluggable-optics": True,
#                     "is-physical": True,
#                     "is-passive": False,
#                     "faceplate-label": "none",
#                 }
#                 self.assertDictEqual(port2_data, port2_expected)

#                 # port16 transceiver (MISSING VENDOR)
#                 port16_data = libyang.xpath_get(
#                     data,
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port16']",
#                 )
#                 port16_expected = {
#                     "circuit-pack-name": "port16",
#                     "vendor": "",
#                     "model": "transceiver_test_model_16",
#                     "serial-id": "transceiver_test_serial_16",
#                     "operational-state": "inService",
#                     "is-pluggable-optics": True,
#                     "is-physical": True,
#                     "is-passive": False,
#                     "faceplate-label": "none",
#                 }
#                 self.assertDictEqual(port16_data, port16_expected)

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_get_base_circuit_pack(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")

#                 base_data = libyang.xpath_get(
#                     data,
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='SYS']",
#                 )
#                 base_expected = {
#                     "circuit-pack-name": "SYS",
#                     "vendor": "test_vendor",
#                     "model": "test_part-number",
#                     "serial-id": "test_serial-number",
#                     "operational-state": "inService",
#                     "is-pluggable-optics": False,
#                     "is-physical": True,
#                     "is-passive": False,
#                     "faceplate-label": "none",
#                 }
#                 self.assertDictEqual(base_data, base_expected)

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_set_info(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:

#                 # test node-id success
#                 sess.switch_datastore("running")
#                 sess.set_item(
#                     "/org-openroadm-device:org-openroadm-device/info/node-id", "a123456"
#                 )
#                 sess.apply_changes()

#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data, "/org-openroadm-device:org-openroadm-device/info/node-id"
#                 )
#                 self.assertEqual(data, "a123456")

#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data, "/org-openroadm-device:org-openroadm-device/info/node-id"
#                 )
#                 self.assertEqual(data, "a123456")

#                 # test node-id fail
#                 sess.switch_datastore("running")
#                 self.assertRaises(
#                     sysrepo.errors.SysrepoInvalArgError,
#                     sess.set_item,
#                     "/org-openroadm-device:org-openroadm-device/info/node-id",
#                     "1",
#                 )

#                 # test node-number
#                 sess.switch_datastore("running")
#                 sess.set_item(
#                     "/org-openroadm-device:org-openroadm-device/info/node-number", 1
#                 )
#                 sess.apply_changes()

#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data, "/org-openroadm-device:org-openroadm-device/info/node-number"
#                 )
#                 self.assertEqual(data, 1)

#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data, "/org-openroadm-device:org-openroadm-device/info/node-number"
#                 )
#                 self.assertEqual(data, 1)

#                 # test node-type
#                 sess.switch_datastore("running")
#                 sess.set_item(
#                     "/org-openroadm-device:org-openroadm-device/info/node-type", "xpdr"
#                 )
#                 sess.apply_changes()

#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data, "/org-openroadm-device:org-openroadm-device/info/node-type"
#                 )
#                 self.assertEqual(data, "xpdr")

#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data, "/org-openroadm-device:org-openroadm-device/info/node-type"
#                 )
#                 self.assertEqual(data, "xpdr")

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_create_shelf(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 # find sys component name
#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/goldstone-platform:components/component")
#                 data = libyang.xpath_get(
#                     data, "/goldstone-platform:components/component"
#                 )
#                 sys_comp_name = next(
#                     (
#                         comp.get("name")
#                         for comp in data
#                         if comp.get("state", {}).get("type") == "SYS"
#                     ),
#                     None,
#                 )

#                 # test provisioning of SYS shelf
#                 sess.switch_datastore("running")
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/shelf-name",
#                     sys_comp_name,
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/shelf-type",
#                     "SYS",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/administrative-state",
#                     "inService",
#                 )
#                 sess.apply_changes()

#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data,
#                     f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']",
#                 )
#                 expected = {
#                     # user provisioned data
#                     "shelf-name": sys_comp_name,
#                     "shelf-type": "SYS",
#                     "administrative-state": "inService",
#                     "operational-state": "inService",
#                     # static read only data
#                     "vendor": "test_vendor",
#                     "model": "test_part-number",
#                     "serial-id": "test_serial-number",
#                     "is-physical": True,
#                     "is-passive": False,
#                     "faceplate-label": "none",
#                 }
#                 self.assertDictEqual(data, expected)

#                 # test failure of arbitrary shelf creation
#                 sess.switch_datastore("running")
#                 sess.set_item(
#                     "/org-openroadm-device:org-openroadm-device/shelves[shelf-name='test_shelf']/shelf-name",
#                     "test_shelf",
#                 )
#                 sess.set_item(
#                     "/org-openroadm-device:org-openroadm-device/shelves[shelf-name='test_shelf']/shelf-type",
#                     "SYS",
#                 )
#                 sess.set_item(
#                     "/org-openroadm-device:org-openroadm-device/shelves[shelf-name='test_shelf']/administrative-state",
#                     "inService",
#                 )

#                 self.assertRaises(
#                     sysrepo.errors.SysrepoCallbackFailedError, sess.apply_changes
#                 )

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_create_circuit_pack(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 # find sys component name
#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/goldstone-platform:components/component")
#                 data = libyang.xpath_get(
#                     data, "/goldstone-platform:components/component"
#                 )
#                 sys_comp_name = next(
#                     (
#                         comp.get("name")
#                         for comp in data
#                         if comp.get("state", {}).get("type") == "SYS"
#                     ),
#                     None,
#                 )

#                 # test provisioning of base circuit-pack
#                 sess.switch_datastore("running")

#                 # provisional required SYS shelf
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/shelf-name",
#                     sys_comp_name,
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/shelf-type",
#                     "SYS",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/administrative-state",
#                     "inService",
#                 )
#                 sess.apply_changes()

#                 # provision base circuit-pack
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/circuit-pack-name",
#                     sys_comp_name,
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/circuit-pack-type",
#                     "test_type",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/administrative-state",
#                     "inService",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/shelf",
#                     sys_comp_name,
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/slot",
#                     "test_slot",
#                 )
#                 sess.apply_changes()

#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data,
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']",
#                 )
#                 expected = {
#                     # user provisioned data
#                     "circuit-pack-name": sys_comp_name,
#                     "circuit-pack-type": "test_type",
#                     "administrative-state": "inService",
#                     "shelf": sys_comp_name,
#                     "slot": "test_slot",
#                     # static read only data
#                     "operational-state": "inService",
#                     "vendor": "test_vendor",
#                     "model": "test_part-number",
#                     "serial-id": "test_serial-number",
#                     "is-pluggable-optics": False,
#                     "is-physical": True,
#                     "is-passive": False,
#                     "faceplate-label": "none",
#                 }
#                 self.assertDictEqual(data, expected)

#                 # test failure of arbitary circuit-pack creation
#                 sess.switch_datastore("running")
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='test_pack']/circuit-pack-name",
#                     "test_pack",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='test_pack']/circuit-pack-type",
#                     "test_type",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='test_pack']/administrative-state",
#                     "inService",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='test_pack']/shelf",
#                     sys_comp_name,
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='test_pack']/slot",
#                     "test_slot",
#                 )

#                 self.assertRaises(
#                     sysrepo.errors.SysrepoCallbackFailedError, sess.apply_changes
#                 )

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_create_circuit_pack_port(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 # find sys component name
#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/goldstone-platform:components/component")
#                 data = libyang.xpath_get(
#                     data, "/goldstone-platform:components/component"
#                 )
#                 sys_comp_name = next(
#                     (
#                         comp.get("name")
#                         for comp in data
#                         if comp.get("state", {}).get("type") == "SYS"
#                     ),
#                     None,
#                 )

#                 # test port provisioning
#                 sess.switch_datastore("running")

#                 # provisional required SYS shelf
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/shelf-name",
#                     sys_comp_name,
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/shelf-type",
#                     "SYS",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/administrative-state",
#                     "inService",
#                 )
#                 sess.apply_changes()

#                 # provision port1 circuit-pack
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/circuit-pack-name",
#                     sys_comp_name,
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/circuit-pack-type",
#                     "test_type",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/administrative-state",
#                     "inService",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/shelf",
#                     sys_comp_name,
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/slot",
#                     "test_slot",
#                 )
#                 sess.apply_changes()

#                 # provision port "1" for port1 circuit-pack
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/ports[port-name='1']/port-name",
#                     "1",
#                 )
#                 sess.apply_changes()

#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data,
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/ports[port-name='1']",
#                 )
#                 expected = {
#                     # user provisioned data
#                     "port-name": "1",
#                     # static read only data
#                     "port-direction": "bidirectional",
#                     "is-physical": True,
#                     "faceplate-label": "none",
#                     "operational-state": "inService",
#                 }
#                 self.assertDictEqual(data, expected)

#                 # test failure of arbitary port-name creation
#                 sess.switch_datastore("running")
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/ports[port-name='test_port']/port-name",
#                     "test_port",
#                 )
#                 self.assertRaises(
#                     sysrepo.errors.SysrepoCallbackFailedError, sess.apply_changes
#                 )
#                 sess.discard_changes()

#                 # test failure of creation of port for non-PIU/TRANSCIEVER circuit-pack
#                 # provision base circuit-pack
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/circuit-pack-name",
#                     sys_comp_name,
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/circuit-pack-type",
#                     "test_type",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/administrative-state",
#                     "inService",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/shelf",
#                     sys_comp_name,
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/slot",
#                     "test_slot",
#                 )
#                 sess.apply_changes()

#                 # test failure of provisioning port for base circuit-pack
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/ports[port-name='1']/port-name",
#                     "1",
#                 )
#                 self.assertRaises(
#                     sysrepo.errors.SysrepoCallbackFailedError, sess.apply_changes
#                 )
#                 sess.discard_changes()

#                 # Test deletion of circuit-packs
#                 sess.switch_datastore("running")

#                 # Get the existing circuit-packs in running datastore
#                 data = sess.get_data(
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs"
#                 )

#                 # Get the list of circuit-pack-name
#                 cp_name_list = libyang.xpath_get(
#                     data,
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs/circuit-pack-name",
#                 )

#                 # delete the circuit-packs in running datastore
#                 for cp_name in cp_name_list:
#                     sess.delete_item(
#                         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{cp_name}']"
#                     )
#                     sess.apply_changes()

#                 # check running datastore that all circuit-packs are deleted
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data, f"/org-openroadm-device:org-openroadm-device/circuit-packs"
#                 )

#                 self.assertEqual(None, data)

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_get_optical_operational_mode_profile(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 profile_data = libyang.xpath_get(
#                     data,
#                     f"/org-openroadm-device:org-openroadm-device/optical-operational-mode-profile",
#                 )

#             # check Open ROADM profile display with the profile list in JSON file
#             for mode in self.server.operational_modes:
#                 my_profile_name = mode.get("openroadm", {}).get("profile-name")
#                 if my_profile_name != None:
#                     self.assertIn(my_profile_name, profile_data)

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#                 data = libyang.xpath_get(
#                     data, "/goldstone-platform:components/component"
#                 )
#                 sys_comp_name = next(
#                     (
#                         comp.get("name")
#                         for comp in data
#                         if comp.get("state", {}).get("type") == "SYS"
#                     ),
#                     None,
#                 )

#                 # test provisioning of base circuit-pack
#                 sess.switch_datastore("running")

#                 # provisional required SYS shelf
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/shelf-name",
#                     sys_comp_name,
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/shelf-type",
#                     "SYS",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/administrative-state",
#                     "inService",
#                 )
#                 sess.apply_changes()

#                 # provision base circuit-pack
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/circuit-pack-name",
#                     sys_comp_name,
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/circuit-pack-type",
#                     "test_type",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/administrative-state",
#                     "inService",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/shelf",
#                     sys_comp_name,
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/slot",
#                     "test_slot",
#                 )
#                 sess.apply_changes()

#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data,
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']",
#                 )
#                 expected = {
#                     # user provisioned data
#                     "circuit-pack-name": sys_comp_name,
#                     "circuit-pack-type": "test_type",
#                     "administrative-state": "inService",
#                     "shelf": sys_comp_name,
#                     "slot": "test_slot",
#                     # static read only data
#                     "operational-state": "inService",
#                     "vendor": "test_vendor",
#                     "model": "test_part-number",
#                     "serial-id": "test_serial-number",
#                     "is-pluggable-optics": False,
#                     "is-physical": True,
#                     "is-passive": False,
#                     "faceplate-label": "none",
#                 }
#                 self.assertDictEqual(data, expected)

#                 # test failure of arbitary circuit-pack creation
#                 sess.switch_datastore("running")
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='test_pack']/circuit-pack-name",
#                     "test_pack",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='test_pack']/circuit-pack-type",
#                     "test_type",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='test_pack']/administrative-state",
#                     "inService",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='test_pack']/shelf",
#                     sys_comp_name,
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='test_pack']/slot",
#                     "test_slot",
#                 )

#                 self.assertRaises(
#                     sysrepo.errors.SysrepoCallbackFailedError, sess.apply_changes
#                 )

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_create_circuit_pack_port(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 # find sys component name
#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/goldstone-platform:components/component")
#                 data = libyang.xpath_get(
#                     data, "/goldstone-platform:components/component"
#                 )
#                 sys_comp_name = next(
#                     (
#                         comp.get("name")
#                         for comp in data
#                         if comp.get("state", {}).get("type") == "SYS"
#                     ),
#                     None,
#                 )

#                 # test port provisioning
#                 sess.switch_datastore("running")

#                 # provisional required SYS shelf
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/shelf-name",
#                     sys_comp_name,
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/shelf-type",
#                     "SYS",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='{sys_comp_name}']/administrative-state",
#                     "inService",
#                 )
#                 sess.apply_changes()

#                 # provision port1 circuit-pack
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/circuit-pack-name",
#                     sys_comp_name,
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/circuit-pack-type",
#                     "test_type",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/administrative-state",
#                     "inService",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/shelf",
#                     sys_comp_name,
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/slot",
#                     "test_slot",
#                 )
#                 sess.apply_changes()

#                 # provision port "1" for port1 circuit-pack
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/ports[port-name='1']/port-name",
#                     "1",
#                 )
#                 sess.apply_changes()

#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data,
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/ports[port-name='1']",
#                 )
#                 expected = {
#                     # user provisioned data
#                     "port-name": "1",
#                     # static read only data
#                     "port-direction": "bidirectional",
#                     "is-physical": True,
#                     "faceplate-label": "none",
#                     "operational-state": "inService",
#                 }
#                 self.assertDictEqual(data, expected)

#                 # test failure of arbitary port-name creation
#                 sess.switch_datastore("running")
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='port1']/ports[port-name='test_port']/port-name",
#                     "test_port",
#                 )
#                 self.assertRaises(
#                     sysrepo.errors.SysrepoCallbackFailedError, sess.apply_changes
#                 )
#                 sess.discard_changes()

#                 # test failure of creation of port for non-PIU/TRANSCIEVER circuit-pack
#                 # provision base circuit-pack
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/circuit-pack-name",
#                     sys_comp_name,
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/circuit-pack-type",
#                     "test_type",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/administrative-state",
#                     "inService",
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/shelf",
#                     sys_comp_name,
#                 )
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/slot",
#                     "test_slot",
#                 )
#                 sess.apply_changes()

#                 # test failure of provisioning port for base circuit-pack
#                 sess.set_item(
#                     f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{sys_comp_name}']/ports[port-name='1']/port-name",
#                     "1",
#                 )
#                 self.assertRaises(
#                     sysrepo.errors.SysrepoCallbackFailedError, sess.apply_changes
#                 )
#                 sess.discard_changes()

#                 # Test deletion of circuit-packs
#                 sess.switch_datastore("running")

#                 # Get the existing circuit-packs in running datastore
#                 data = sess.get_data(
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs"
#                 )

#                 # Get the list of circuit-pack-name
#                 cp_name_list = libyang.xpath_get(
#                     data,
#                     "/org-openroadm-device:org-openroadm-device/circuit-packs/circuit-pack-name",
#                 )

#                 # delete the circuit-packs in running datastore
#                 for cp_name in cp_name_list:
#                     sess.delete_item(
#                         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{cp_name}']"
#                     )
#                     sess.apply_changes()

#                 # check running datastore that all circuit-packs are deleted
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 data = libyang.xpath_get(
#                     data, f"/org-openroadm-device:org-openroadm-device/circuit-packs"
#                 )

#                 self.assertEqual(None, data)

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#     async def test_get_optical_operational_mode_profile(self):
#         def test():
#             time.sleep(2)  # wait for the mock server
#             with self.conn.start_session() as sess:
#                 sess.switch_datastore("operational")
#                 data = sess.get_data("/org-openroadm-device:org-openroadm-device")
#                 profile_data = libyang.xpath_get(
#                     data,
#                     f"/org-openroadm-device:org-openroadm-device/optical-operational-mode-profile",
#                 )

#             # check Open ROADM profile display with the profile list in JSON file
#             for mode in self.server.operational_modes:
#                 my_profile_name = mode.get("openroadm", {}).get("profile-name")
#                 if my_profile_name != None:
#                     self.assertIn(my_profile_name, profile_data)

#         self.tasks.append(asyncio.to_thread(test))
#         tasks = [
#             t if isinstance(t, asyncio.Task) else asyncio.create_task(t)
#             for t in self.tasks
#         ]

#         done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
#         for task in done:
#             e = task.exception()
#             if e:
#                 raise e

#         f"/org-openroadm-device:org-openroadm-device/interface[name='{if_name}']/administrative-state",
#         "inService",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/interface[name='{if_name}']/supporting-port",
#         "1",
#     )
#     if sup_intf:
#         sess.set_item(
#             f"/org-openroadm-device:org-openroadm-device/interface[name='{if_name}']/supporting-interface-list",
#             sup_intf,
#         )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{cp_name}']/subSlot",
#         f"{cp_name}",
#     )
#     sess.apply_changes()


# def setup_circuit_pack(sess, cp_name, shelf="SYS", slot="1"):
#     """Setup/provision required leaves for OpenROADM interface.

#     Args:
#         sess (SysrepoSession): Sysrepo session used to make changes.
#         cp_name (str): Name of the OpenROADM circuit-pack to provision
#         slot (str): Name of the slot to provision for the OpenROADM circuit-pack
#         shelf (str): Name of shelf. Must already be provisioned.
#     """
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{cp_name}']/circuit-pack-type",
#         "cpType",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{cp_name}']/administrative-state",
#         "inService",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{cp_name}']/shelf",
#         "SYS",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{cp_name}']/slot",
#         f"{slot}",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{cp_name}']/ports[port-name='1']",
#         "1",
#     )
#     sess.apply_changes()


# def setup_otsi_connections(sess, piu, ori, slot):
#     """Sets up circuit-pack and interface for PIU.

#     Args:
#         sess (SysrepoSession): Sysrepo session used to make changes.
#         piu (str): Name of the piu. Used to provision OpenROADM circuit-pack.
#         ori (str): Name of the OpenROADM interface to provision (opaque outside of OpenROADM).
#         slot (str): Name of slot to provision for OpenROADM circuit-pack.
#     """
#     # setup circuit-pack
#     setup_circuit_pack(sess, piu, slot=slot)

#     # setup interface
#     setup_interface(sess, ori, piu)


# def setup_shelf_and_sys(sess):
#     """Perform general shelf and SYS circuit-pack configuration

#     Args:
#         sess (SysrepoSession): Sysrepo session used to make changes.
#     """
#     # Setup basic shelf info to start with
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='SYS']/shelf-type",
#         "myshelftype",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='SYS']/administrative-state",
#         "inService",
#     )
#     sess.apply_changes()

#     # And the overall SYS circuit-pack
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='SYS']/circuit-pack-name",
#         "SYS",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='SYS']/circuit-pack-type",
#         "SYScpType",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='SYS']/administrative-state",
#         "inService",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='SYS']/shelf",
#         "SYS",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='SYS']/slot",
#         0,
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='SYS']/subSlot",
#         0,
#     )
#     sess.apply_changes()


# def setup_eth_port_config(sess, slot, piu, if_name, or_port):
#     """
#     Perform ethernet circuit pack and interface configuration
#     """
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{piu}']/circuit-pack-type",
#         "PIUcpType",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{piu}']/administrative-state",
#         "inService",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{piu}']/shelf",
#         "SYS",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{piu}']/slot",
#         f"{slot}",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{piu}']/subSlot",
#         f"{piu}",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{piu}']/parent-circuit-pack/circuit-pack-name",
#         "SYS",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{piu}']/parent-circuit-pack/cp-slot-name",
#         f"{piu}",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{piu}']/ports[port-name='1']/port-name",
#         1,
#     )
#     sess.apply_changes()

#     # Next define the portX circuit pack
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{or_port}']/circuit-pack-type",
#         "PortXcpType",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{or_port}']/administrative-state",
#         "inService",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{or_port}']/shelf",
#         "SYS",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{or_port}']/slot",
#         f"{slot}",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{or_port}']/subSlot",
#         f"{or_port}",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{or_port}']/parent-circuit-pack/circuit-pack-name",
#         "SYS",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{or_port}']/parent-circuit-pack/cp-slot-name",
#         f"{or_port}",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{or_port}']/ports[port-name='1']/port-name",
#         1,
#     )
#     sess.apply_changes()

#     # Create the interface items.
#     # Note that this interface name is meaningful only to openroadm
#     # However, it must be unique within the system scope
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/interface[name='{if_name}']/type",
#         "org-openroadm-interfaces:ethernetCsmacd",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/interface[name='{if_name}']/administrative-state",
#         "inService",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/interface[name='{if_name}']/supporting-circuit-pack-name",
#         f"{or_port}",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/interface[name='{if_name}']/supporting-port",
#         1,
#     )
#     sess.apply_changes()


# def setup_interface_hierarchy(sess):
#     """Sets up OpenROADM interface hierarchy."""

#     # setup 'SYS' shelf
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='SYS']/shelf-type",
#         "SYS",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/shelves[shelf-name='SYS']/administrative-state",
#         "inService",
#     )

#     # setup circuit-pack and otsi interface
#     setup_otsi_connections(sess, "piu1", "otsi-piu1", "1")
#     sess.set_item(
#         "/org-openroadm-device:org-openroadm-device/interface[name='otsi-piu1']/org-openroadm-optical-tributary-signal-interfaces:otsi/otsi-rate",
#         "org-openroadm-common-optical-channel-types:R400G-otsi",
#     )

#     # setup circuit-pack and otsi-g interface
#     # supporting-circuit-pack-name will be derived from supporting-interface-list for high-level-interfaces in Phase 2
#     setup_interface(
#         sess,
#         "otsig-piu1",
#         "piu1",
#         type="org-openroadm-interfaces:otsi-group",
#         sup_intf="otsi-piu1",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/interface[name='otsig-piu1']/org-openroadm-otsi-group-interfaces:otsi-group/group-rate",
#         "org-openroadm-common-optical-channel-types:R400G-otsi",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/interface[name='otsig-piu1']/org-openroadm-otsi-group-interfaces:otsi-group/group-id",
#         1,
#     )

#     # setup otuc interface
#     setup_interface(
#         sess,
#         "otuc-piu1",
#         "piu1",
#         type="org-openroadm-interfaces:otnOtu",
#         sup_intf="otsig-piu1",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/interface[name='otuc-piu1']/org-openroadm-otn-otu-interfaces:otu/rate",
#         "org-openroadm-otn-common-types:OTUCn",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/interface[name='otuc-piu1']/org-openroadm-otn-otu-interfaces:otu/otucn-n-rate",
#         4,
#     )

#     # setup oduc interface
#     setup_interface(
#         sess,
#         "oduc-piu1",
#         "piu1",
#         type="org-openroadm-interfaces:otnOdu",
#         sup_intf="otuc-piu1",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/interface[name='oduc-piu1']/org-openroadm-otn-odu-interfaces:odu/rate",
#         "org-openroadm-otn-common-types:ODUCn",
#     )
#     sess.set_item(
#         f"/org-openroadm-device:org-openroadm-device/interface[name='oduc-piu1']/org-openroadm-otn-odu-interfaces:odu/oducn-n-rate",
#         4,
#     )

#     sess.apply_changes()
