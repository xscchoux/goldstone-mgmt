import argparse
import asyncio
import itertools
import json
import logging
import signal

import sysrepo

from .device import DeviceServer
from .pm import PMServer

logger = logging.getLogger(__name__)


def load_operational_modes(operational_modes_file):
    try:
        with open(operational_modes_file, "r") as f:
            return json.loads(f.read())
    except json.decoder.JSONDecodeError as e:
        logger.error("Invalid configuration file %s.", operational_modes_file)
        raise e
    except FileNotFoundError as e:
        logger.error("Configuration file %s is not found.", operational_modes_file)
        raise e


def main():
    async def _main(operational_modes):
        loop = asyncio.get_event_loop()
        stop_event = asyncio.Event()
        loop.add_signal_handler(signal.SIGINT, stop_event.set)
        loop.add_signal_handler(signal.SIGTERM, stop_event.set)

        conn = sysrepo.SysrepoConnection()
        servers = [
            DeviceServer(conn, operational_modes),
            PMServer(conn),
        ]

        try:
            tasks = list(
                itertools.chain.from_iterable([await s.start() for s in servers])
            )
            tasks.append(stop_event.wait())
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            logger.debug(f"done: {done}, pending: {pending}")
            for task in done:
                e = task.exception()
                if e:
                    raise e
        finally:
            for s in servers:
                s.stop()
            conn.disconnect()

    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "operational_modes_file",
        metavar="operational-modes-file",
        help="path to operational-modes config file",
    )
    args = parser.parse_args()

    fmt = "%(levelname)s %(module)s %(funcName)s l.%(lineno)d | %(message)s"
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format=fmt)
    #        sysrepo.configure_logging(py_logging=True)
    else:
        logging.basicConfig(level=logging.INFO, format=fmt)

    operational_modes = load_operational_modes(args.operational_modes_file)

    asyncio.run(_main(operational_modes))


if __name__ == "__main__":
    main()
