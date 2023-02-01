import asyncio

import libyang
import sysrepo
from goldstone.lib.core import *

OPERATIONAL_MODES_PATH = (
    os.path.dirname(__file__) + "/../../../../scripts/operational-modes.json"
)


class MockGSPlatformServer(ServerBase):
    def __init__(self, conn):
        super().__init__(conn, "goldstone-platform")
        self.handlers = {}

    def oper_cb(self, xpath, priv):
        # mock goldstone-platform data here
        components = [
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
        return {"components": {"component": components}}


def run_mock_gs_platformserver(q):
    conn = sysrepo.SysrepoConnection()
    server = MockGSPlatformServer(conn)

    async def _main():
        tasks = await server.start()

        async def evloop():
            while True:
                await asyncio.sleep(1)
                try:
                    q.get(False)
                except:
                    pass
                else:
                    return

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


class MockGSTransponderServer(ServerBase):
    def __init__(self, conn):
        super().__init__(conn, "goldstone-transponder")
        self.handlers = {
            "modules": {
                "module": {
                    "name": NoOp,
                    "config": {
                        "name": NoOp,
                    },
                    "network-interface": {
                        "name": NoOp,
                        "config": {
                            "name": NoOp,
                            "output-power": NoOp,
                            "line-rate": NoOp,
                            "modulation-format": NoOp,
                            "fec-type": NoOp,
                            "tx-laser-freq": NoOp,
                            "loopback-type": NoOp,
                        },
                    },
                    "host-interface": {
                        "name": NoOp,
                        "config": {
                            "name": NoOp,
                            "signal-rate": NoOp,
                            "fec-type": NoOp,
                        },
                    },
                }
            }
        }

    def oper_cb(self, xpath, priv):
        # mock goldstone-transponder data here
        modules = [
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
        return {"modules": {"module": modules}}


def run_mock_gs_transponderserver(q):
    conn = sysrepo.SysrepoConnection()
    server = MockGSTransponderServer(conn)

    async def _main():
        tasks = await server.start()

        async def evloop():
            while True:
                await asyncio.sleep(1)
                try:
                    q.get(False)
                except:
                    pass
                else:
                    return

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


def setup_interface(
    sess, if_name, cp_name, type="org-openroadm-interfaces:otsi", sup_intf=None
):
    """Setup/provision required leaves for OpenROADM interface.

    Args:
        sess (SysrepoSession): Sysrepo session used to make changes.
        ori (str): Name of the OpenROADM interface to provision (opaque outside of OpenROADM)
        cp_name (str): Name of supporting-circuit-pack. Must already be provisioned.
        sup_intf (str): Name of supporting interface. Must already be provisioned.
    """
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/interface[name='{if_name}']/supporting-circuit-pack-name",
        f"{cp_name}",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/interface[name='{if_name}']/type",
        type,
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/interface[name='{if_name}']/administrative-state",
        "inService",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/interface[name='{if_name}']/supporting-port",
        "1",
    )
    if sup_intf:
        sess.set_item(
            f"/org-openroadm-device:org-openroadm-device/interface[name='{if_name}']/supporting-interface-list",
            sup_intf,
        )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{cp_name}']/subSlot",
        f"{cp_name}",
    )
    sess.apply_changes()


def setup_circuit_pack(sess, cp_name, shelf="SYS", slot="1"):
    """Setup/provision required leaves for OpenROADM interface.

    Args:
        sess (SysrepoSession): Sysrepo session used to make changes.
        cp_name (str): Name of the OpenROADM circuit-pack to provision
        slot (str): Name of the slot to provision for the OpenROADM circuit-pack
        shelf (str): Name of shelf. Must already be provisioned.
    """
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{cp_name}']/circuit-pack-type",
        "cpType",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{cp_name}']/administrative-state",
        "inService",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{cp_name}']/shelf",
        "SYS",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{cp_name}']/slot",
        f"{slot}",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{cp_name}']/ports[port-name='1']",
        "1",
    )
    sess.apply_changes()


def setup_otsi_connections(sess, piu, ori, slot):
    """Sets up circuit-pack and interface for PIU.

    Args:
        sess (SysrepoSession): Sysrepo session used to make changes.
        piu (str): Name of the piu. Used to provision OpenROADM circuit-pack.
        ori (str): Name of the OpenROADM interface to provision (opaque outside of OpenROADM).
        slot (str): Name of slot to provision for OpenROADM circuit-pack.
    """
    # setup circuit-pack
    setup_circuit_pack(sess, piu, slot=slot)

    # setup interface
    setup_interface(sess, ori, piu)


def setup_shelf_and_sys(sess):
    """Perform general shelf and SYS circuit-pack configuration

    Args:
        sess (SysrepoSession): Sysrepo session used to make changes.
    """
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

    # And the overall SYS circuit-pack
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='SYS']/circuit-pack-name",
        "SYS",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='SYS']/circuit-pack-type",
        "SYScpType",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='SYS']/administrative-state",
        "inService",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='SYS']/shelf",
        "SYS",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='SYS']/slot",
        0,
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='SYS']/subSlot",
        0,
    )
    sess.apply_changes()


def setup_eth_port_config(sess, slot, piu, if_name, or_port):
    """
    Perform ethernet circuit pack and interface configuration
    """
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{piu}']/circuit-pack-type",
        "PIUcpType",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{piu}']/administrative-state",
        "inService",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{piu}']/shelf",
        "SYS",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{piu}']/slot",
        f"{slot}",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{piu}']/subSlot",
        f"{piu}",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{piu}']/parent-circuit-pack/circuit-pack-name",
        "SYS",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{piu}']/parent-circuit-pack/cp-slot-name",
        f"{piu}",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{piu}']/ports[port-name='1']/port-name",
        1,
    )
    sess.apply_changes()

    # Next define the portX circuit pack
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{or_port}']/circuit-pack-type",
        "PortXcpType",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{or_port}']/administrative-state",
        "inService",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{or_port}']/shelf",
        "SYS",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{or_port}']/slot",
        f"{slot}",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{or_port}']/subSlot",
        f"{or_port}",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{or_port}']/parent-circuit-pack/circuit-pack-name",
        "SYS",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{or_port}']/parent-circuit-pack/cp-slot-name",
        f"{or_port}",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/circuit-packs[circuit-pack-name='{or_port}']/ports[port-name='1']/port-name",
        1,
    )
    sess.apply_changes()

    # Create the interface items.
    # Note that this interface name is meaningful only to openroadm
    # However, it must be unique within the system scope
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/interface[name='{if_name}']/type",
        "org-openroadm-interfaces:ethernetCsmacd",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/interface[name='{if_name}']/administrative-state",
        "inService",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/interface[name='{if_name}']/supporting-circuit-pack-name",
        f"{or_port}",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/interface[name='{if_name}']/supporting-port",
        1,
    )
    sess.apply_changes()


def setup_interface_hierarchy(sess):
    """Sets up OpenROADM interface hierarchy."""

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
    setup_otsi_connections(sess, "piu1", "otsi-piu1", "1")
    sess.set_item(
        "/org-openroadm-device:org-openroadm-device/interface[name='otsi-piu1']/org-openroadm-optical-tributary-signal-interfaces:otsi/otsi-rate",
        "org-openroadm-common-optical-channel-types:R400G-otsi",
    )

    # setup circuit-pack and otsi-g interface
    # supporting-circuit-pack-name will be derived from supporting-interface-list for high-level-interfaces in Phase 2
    setup_interface(
        sess,
        "otsig-piu1",
        "piu1",
        type="org-openroadm-interfaces:otsi-group",
        sup_intf="otsi-piu1",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/interface[name='otsig-piu1']/org-openroadm-otsi-group-interfaces:otsi-group/group-rate",
        "org-openroadm-common-optical-channel-types:R400G-otsi",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/interface[name='otsig-piu1']/org-openroadm-otsi-group-interfaces:otsi-group/group-id",
        1,
    )

    # setup otuc interface
    setup_interface(
        sess,
        "otuc-piu1",
        "piu1",
        type="org-openroadm-interfaces:otnOtu",
        sup_intf="otsig-piu1",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/interface[name='otuc-piu1']/org-openroadm-otn-otu-interfaces:otu/rate",
        "org-openroadm-otn-common-types:OTUCn",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/interface[name='otuc-piu1']/org-openroadm-otn-otu-interfaces:otu/otucn-n-rate",
        4,
    )

    # setup oduc interface
    setup_interface(
        sess,
        "oduc-piu1",
        "piu1",
        type="org-openroadm-interfaces:otnOdu",
        sup_intf="otuc-piu1",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/interface[name='oduc-piu1']/org-openroadm-otn-odu-interfaces:odu/rate",
        "org-openroadm-otn-common-types:ODUCn",
    )
    sess.set_item(
        f"/org-openroadm-device:org-openroadm-device/interface[name='oduc-piu1']/org-openroadm-otn-odu-interfaces:odu/oducn-n-rate",
        4,
    )

    sess.apply_changes()