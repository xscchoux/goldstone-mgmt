import argparse

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit import patch_stdout

import sys
import logging
import asyncio

from .root import Root
from .base import BreakLoop

from goldstone.lib.connector.sysrepo import Connector as SysrepoConnector
from goldstone.lib.connector.netconf import Connector as NETCONFConnector
from goldstone.lib.errors import Error

from . import interface
from . import platform
from . import transponder
from . import system
from . import ufd
from . import portchannel
from . import vlan
from . import management_interface
from . import gearbox
from . import dpll

stdout = logging.getLogger("stdout")
stderr = logging.getLogger("stderr")


class GoldstoneShell(object):
    def __init__(self, conn, default_prompt="> ", prefix=""):
        self.context = Root(conn)
        self.default_input = ""
        self.default_prompt = default_prompt
        self.prefix = prefix

    def prompt(self):
        c = self.context
        l = [str(c)]
        while c.parent:
            l.append(str(c.parent))
            c = c.parent
        return (
            self.prefix
            + ("/".join(reversed(l))[1:] if len(l) > 1 else "")
            + self.default_prompt
        )

    def completer(self):
        return self.context.completer

    async def exec(self, cmd: list, no_fail=True):
        ret = self.context.exec(cmd, no_fail=no_fail)
        if ret:
            self.context = ret
        self.default_input = ""

    def bindings(self):
        b = KeyBindings()

        @b.add("?")
        def _(event):
            buf = event.current_buffer
            original_text = buf.text
            help_msg = event.app.shell.context.help(buf.text)
            buf.insert_text("?")
            buf.insert_line_below(copy_margin=False)
            buf.insert_text(help_msg)
            event.app.exit("")
            event.app.shell.default_input = original_text

        #        @b.add(' ')
        #        def _(event):
        #            buf = event.current_buffer
        #            if len(buf.text.strip()) > 0 and len(buf.text) == buf.cursor_position:
        #                candidates = list(event.app.shell.context.completion(buf.document))
        #                if len(candidates) == 1:
        #                    c = candidates[0]
        #                    buf.insert_text(c.text[-c.start_position:])
        #                buf.cancel_completion()
        #            buf.insert_text(' ')

        return b


async def loop_async(shell):
    session = PromptSession()

    with patch_stdout.patch_stdout():
        while True:
            c = shell.completer()
            p = shell.prompt()
            b = shell.bindings()
            session.app.shell = shell
            try:
                line = await session.prompt_async(
                    p, completer=c, key_bindings=b, default=shell.default_input
                )
            except KeyboardInterrupt:
                stderr.info("Execute 'exit' to exit")
                continue

            if len(line) > 0:
                await shell.exec(line)


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("-c", "--command-string")
    parser.add_argument("-k", "--keep-open", action="store_true")
    parser.add_argument("-x", "--stdin", action="store_true")
    parser.add_argument(
        "--connector", choices=["sysrepo", "netconf"], default="sysrepo"
    )
    parser.add_argument("--connector-opts", default="")

    args = parser.parse_args(args)

    formatter = logging.Formatter(
        "[%(asctime)s][%(levelname)-5s][%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger = logging.getLogger("goldstone")
    logger.addHandler(console)
    console.setLevel(logging.DEBUG)  # emit all messages sent to this handler
    v = args.verbose
    if v == 0:
        logger.setLevel(logging.ERROR)
    elif v == 1:
        logger.setLevel(logging.INFO)
    else:  # v > 1
        logger.setLevel(logging.DEBUG)

    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.DEBUG)
    shf = logging.Formatter("%(message)s")
    sh.setFormatter(shf)

    stdout.setLevel(logging.DEBUG)
    stdout.addHandler(sh)

    sh2 = logging.StreamHandler(sys.stderr)
    sh2.setLevel(logging.DEBUG)
    sh2.setFormatter(shf)

    stderr.setLevel(logging.DEBUG)
    stderr.addHandler(sh2)

    opts = {}
    if args.connector_opts:
        for o in args.connector_opts.split(","):
            v = o.split("=")
            if len(v) != 2:
                stderr.info(f"invalid connector-opts format: '{o}'")
                sys.exit(1)
            opts[v[0]] = v[1]

    try:
        if args.connector == "sysrepo":
            conn = SysrepoConnector()
            prefix = ""
        elif args.connector == "netconf":
            conn = NETCONFConnector(**opts)
            prefix = f"netconf({opts['host']})|"
    except Error as e:
        stderr.info(f"failed to create {args.connector} connector: {e}")
        sys.exit(1)

    shell = GoldstoneShell(conn, prefix=prefix)

    async def _main():

        if args.stdin or args.command_string:
            stream = sys.stdin if args.stdin else args.command_string.split(";")
            for line in stream:
                try:
                    await shell.exec(line, no_fail=False)
                except Error as e:
                    stderr.info("failed to execute: {}".format(line))
                    stderr.info(e)
                    sys.exit(1)
            if not args.keep_open:
                return

        tasks = [loop_async(shell)]

        try:
            await asyncio.gather(*tasks)
        except BreakLoop:
            return

    asyncio.run(_main())


if __name__ == "__main__":
    main()
