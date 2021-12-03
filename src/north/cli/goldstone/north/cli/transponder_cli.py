from .base import InvalidInput, Completer, Command
from .cli import GSObject as Object
from .cli import ShowCommand
from prompt_toolkit.completion import WordCompleter
from .common import sysrepo_wrap, print_tabular
import sysrepo as sr
import libyang as ly
import logging
from tabulate import tabulate
from natsort import natsorted
import re
import base64
import struct

logger = logging.getLogger(__name__)
stdout = logging.getLogger("stdout")
stderr = logging.getLogger("stderr")

_FREQ_RE = re.compile(r".+[kmgt]?hz$")


def human_freq(item):
    if type(item) == str:
        try:
            int(item)
            return item
        except ValueError:
            item = item.lower()
            if not _FREQ_RE.match(item):
                raise InvalidInput("invalid frequency input. (e.g 193.50THz)")
            item = item[:-2]
            multiplier = 1
            if item[-1] == "t":
                multiplier = 1e12
            elif item[-1] == "g":
                multiplier = 1e9
            elif item[-1] == "m":
                multiplier = 1e6
            elif item[-1] == "k":
                multiplier = 1e3
            return str(round(float(item[:-1]) * multiplier))
    else:
        return "{0:.2f}THz".format(int(item) / 1e12)


def human_ber(item):
    return "{0:.2e}".format(struct.unpack(">f", base64.b64decode(item))[0])


def to_human(d, runconf=False):
    for key in d:
        if key.endswith("-ber"):
            d[key] = human_ber(d[key])
        elif "freq" in key:
            d[key] = human_freq(d[key])
        elif type(d[key]) == bool:
            d[key] = "true" if d[key] else "false"
        elif not runconf and key.endswith("power"):
            d[key] = f"{d[key]:.2f} dBm"
        elif type(d[key]) == ly.keyed_list.KeyedList:
            d[key] = ", ".join(d[key])

    return d


class TransponderCommand(Command):
    def __init__(self, context, node):
        self.node = node
        super().__init__(context, name=node.name())

    def exec(self, line):
        if len(line) < 1:
            raise InvalidInput(self.usage())

        enum_values = self.list()
        if len(enum_values) and line[0] not in enum_values:
            raise InvalidInput(self.usage())

        if self.node.name() == "tx-laser-freq":
            value = human_freq(line[0])
        else:
            value = line[0]

        self.context.set(self.node, value)

    def list(self):
        if str(self.node.type()) == "boolean":
            return ["true", "false"]
        return [v[0] for v in self.node.type().all_enums() if v[0] != "unknown"]

    def usage(self):
        enum_values = self.list()
        v = f"<{self.node.type()}>"
        if len(enum_values):
            v = "[" + "|".join(enum_values) + "]"
        return f"usage: {self.node.name()} {v}"


class TransponderNoCommand(Command):
    def __init__(self, context, node):
        self._list = [v.name() for v in node if v.name() != "name"]
        if "admin-status" in self._list:
            self._list.append("shutdown")
        super().__init__(context, name="no")

    def exec(self, line):
        if len(line) < 1:
            raise InvalidInput(self.usage())

        if line[0] not in self.list():
            raise InvalidInput(self.usage())

        # special handling for "shutdown", backward compatibility
        if line[0] == "shutdown":
            self.context.set("admin-status", "up")
        else:
            self.context.delete(line[0])

    def list(self):
        return self._list

    def usage(self):
        return f"usage: no [{'|'.join(self.list())}]"


class TransponderBaseObject(Object):
    def __init__(self, conn, parent):
        super().__init__(parent, fuzzy_completion=True)

        self.session = conn.start_session()
        self.sr_op = sysrepo_wrap(self.session)
        ctx = self.session.get_ly_ctx()

        node = [n for n in ctx.find_path(self.CONFIG_XPATH)]
        assert len(node) == 1
        node = node[0]

        for v in node:
            if v.name() == "name":
                continue
            self.add_command(TransponderCommand(self, v))

        self.add_command(TransponderNoCommand(self, node))

    def set(self, node, value):
        if type(node) == str:
            name = node
        else:
            name = node.name()
        try:
            self.sr_op.get_data(self.module_xpath(), "running")
        except sr.SysrepoNotFoundError as e:
            self.sr_op.set_data(
                f"{self.module_xpath()}/config/name", self.module_name()
            )

        try:
            self.sr_op.get_data(self.xpath(), "running")
        except sr.SysrepoNotFoundError as e:
            self.sr_op.set_data(f"{self.xpath()}/config/name", self.name)

        self.sr_op.set_data(f"{self.xpath()}/config/{name}", value)

    def delete(self, name):
        self.sr_op.delete_data(f"{self.xpath()}/config/{name}")


class TransponderShowCommand(ShowCommand):
    SUBCOMMAND_DICT = {
        "details": Command,
    }
    OBJECT_TYPE = ""
    DETAILED_ATTRS = []
    SKIP_ATTRS = ["index", "location"]

    def exec(self, line):
        ctx = self.context
        if len(line) != 0:
            if line[0] == "details":
                return self.show(detail=True)
            return ctx.root().show(line)

        self.show()

    def show(self, detail=False):
        ctx = self.context

        xpath = ctx.xpath()

        try:
            data = ctx.sr_op.get_data(xpath, "operational")
        except sr.SysrepoNotFoundError as e:
            stderr.info("Not able to fetch data from operational database")
            return
        try:
            data = data["modules"]["module"]
            if self.OBJECT_TYPE == "module":
                data = data[ctx.name]["state"]
            else:
                data = data[ctx.parent.name][self.OBJECT_TYPE][ctx.name]["state"]

            data = to_human(data)

            table = []
            for k, v in data.items():
                if k in self.SKIP_ATTRS:
                    continue
                if not detail and k in self.DETAILED_ATTRS:
                    continue

                table.append([k, v])
            stdout.info(tabulate(table))
        except KeyError as e:
            stderr.info(f"Error while fetching values from operational database: {e}")
            return


class HostIfShowCommand(TransponderShowCommand):
    OBJECT_TYPE = "host-interface"


class NetIfShowCommand(TransponderShowCommand):
    OBJECT_TYPE = "network-interface"
    DETAILED_ATTRS = [
        "pulse-shaping-tx",
        "pulse-shaping-rx",
        "pulse-shaping-tx-beta",
        "pulse-shaping-rx-beta",
        "losi",
        "laser-grid-support",
        "disable-constellation",
        "custom-trb100-rx-power-low-warning-threshold",
        "custom-trb100-rx-power-low-alarm-threshold",
        "custom-trb100-rx-los",
        "ber-period",
        "current-ber-period",
    ]


class ModuleShowCommand(TransponderShowCommand):
    OBJECT_TYPE = "module"


class HostIf(TransponderBaseObject):
    CONFIG_XPATH = "".join(
        f"/goldstone-transponder:{v}"
        for v in ["modules", "module", "host-interface", "config"]
    )

    def module_xpath(self):
        return self.parent.xpath()

    def xpath(self):
        return f"{self.module_xpath()}/host-interface[name='{self.name}']"

    def module_name(self):
        return self.parent.name

    def __init__(self, conn, parent, name):
        super().__init__(conn, parent)
        self.name = name
        self.add_command(HostIfShowCommand(self))

    def __str__(self):
        return "hostif({})".format(self.name)


class NetIf(TransponderBaseObject):
    CONFIG_XPATH = "".join(
        f"/goldstone-transponder:{v}"
        for v in ["modules", "module", "network-interface", "config"]
    )

    def module_xpath(self):
        return self.parent.xpath()

    def xpath(self):
        return f"{self.module_xpath()}/network-interface[name='{self.name}']"

    def module_name(self):
        return self.parent.name

    def __init__(self, conn, parent, name):
        super().__init__(conn, parent)
        self.name = name
        self.add_command(NetIfShowCommand(self))

    def __str__(self):
        return "netif({})".format(self.name)


class TransponderObject(TransponderBaseObject):
    XPATH = "/goldstone-transponder:modules/module"
    CONFIG_XPATH = "".join(
        f"/goldstone-transponder:{v}" for v in ["modules", "module", "config"]
    )

    def module_xpath(self):
        return f"{self.XPATH}[name='{self.name}']"

    def xpath(self):
        return self.module_xpath()

    def module_name(self):
        return self.name

    def __init__(self, conn, parent, name):
        super().__init__(conn, parent)
        self.name = name
        self.command_list = ["shutdown"]

        @self.command(WordCompleter(self.netifs))
        def netif(args):
            if len(args) != 1:
                raise InvalidInput("usage: netif <name>")
            elif args[0] not in self.netifs():
                raise InvalidInput(f"No network interface with name {args[0]}")
            return NetIf(conn, self, args[0])

        @self.command(WordCompleter(self.hostifs))
        def hostif(args):
            if len(args) != 1:
                raise InvalidInput("usage: hostif <name>")
            elif args[0] not in self.hostifs():
                raise InvalidInput(f"No host interface with name {args[0]}")
            return HostIf(conn, self, args[0])

        @self.command()
        def shutdown(args):
            if len(args) != 0:
                raise InvalidInput("usage: shutdown")
            self.set("admin-status", "down")

        self.add_command(ModuleShowCommand(self))

    def netifs(self):
        return self.components("network-interface")

    def hostifs(self):
        return self.components("host-interface")

    def components(self, type_):
        xpath = f"{self.XPATH}[name='{self.name}']/{type_}/name"
        d = self.sr_op.get_data(xpath, "operational")
        d = d.get("modules", {}).get("module", {}).get(self.name, {})
        return natsorted(v["name"] for v in d.get(type_, []))

    def __str__(self):
        return "transponder({})".format(self.name)