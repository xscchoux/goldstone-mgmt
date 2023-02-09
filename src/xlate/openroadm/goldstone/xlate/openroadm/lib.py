from abc import abstractmethod
import logging
import asyncio
import libyang
from goldstone.lib.core import ChangeHandler, ServerBase
from goldstone.lib.errors import Error, InvalArgError, NotFoundError


logger = logging.getLogger(__name__)


class OpenROADMObjectFactory:
    """Factory base for OpenConfig translators.
    It creates OpenConfig objects from Goldstone operational state data. The source Goldstone data are provided by its
    user. A created object may have references to another created object.
    It is an abstract class. You should implement a subclass for each OpenConfig object type. You should also implement
    a subclass for each device type (and/or a set of supported Goldstone native/primitive models). Because a subclass
    hides knowledge of object creation and association rules from its user. The knowledge includes what kind of
    Goldstone data are used and how to use them.
    """

    @abstractmethod
    def required_data(self):
        """Return required data list to create OpenConfig objects.
        Returns:
            list: List of required data dictionaries.
                Attributes in a dictionary.
                    "name": Name of the data.
                        It will be used as a key of the dictionary "gs" the argument of the create().
                    "xpath": Path to get the data.
                    "default": Default value if the data is not found.
        """
        pass

    @abstractmethod
    def create(self, gs):
        """Create OpenConfig objects from Goldstone data.
        Args:
            gs (dict): Data from Goldstone native/primitive models.
        Returns:
            list: List of dictionalies. Each dictionaly represents an OpenConfig object.
        """
        pass


class OpenROADMServer(ServerBase):
    """Server base for OpenROADM translators.
    You can provide an OpenROADM service for "module" by implementing attributes "handlers" and "objects" as a
    subclass.
    A subclass should not aware that which Goldstone data are required and how to use them. The knowledge should be a
    part of "OpenConfigObjectFactory"s and "OpenConfigChangeHandler"s. A subclass has one or multiple
    "OpenConfigObjectFactory"s to create operational state for the service. A subclass has one or multiple
    "OpenConfigChangeHandler"s to apply configuration state change to device's actual configuration.
    If you want to provide user attributes to "OpenConfigChangeHandler"s, you should override pre() and set items to
    "user".
    Args:
        conn (Connector): Connection to the central datastore.
        module (str): YANG module name of the service. e.g. "openconfig-interfaces"
        reconciliation_interval (int): Interval seconds between executions of the reconcile task.
    Attributes:
        conn (Connector): Connection to the central datastore.
        reconciliation_interval (int): Interval seconds between executions of the reconcile task.
        reconcile_task (Task): Reconcile task instance.
        handlers (dict): "OpenConfigChangeHandler"s for each configurable OpenConfig path.
            e.g.
            {
                "interfaces": {
                    "interface": {
                        "config": {
                            "enabled": EnabledHandler # => EnableHandler for /interfaces/interface/config/enabled
                        }
                    }
                }
            }
        objects (dict): "OpenConfigObjectFactory" instances for each OpenConfig subtree.
            e.g.
            {
                "interfaces": {
                    "interface": InterfaceFactory(ComponentNameResolver()) # InterfaceFactory for /interfaces/interface
                }
            }
    """

    def __init__(self, conn, module, reconciliation_interval=10):
        super().__init__(conn, module)
        self.reconciliation_interval = reconciliation_interval
        self.reconcile_task = None
        self.handlers = {}
        self.objects = {}

    async def reconcile(self):
        """Reconcile between OpenConfig configuration state and Goldstone configuration state."""
        pass

    async def reconcile_loop(self):
        """Reconcile task coroutine."""
        while True:
            await asyncio.sleep(self.reconciliation_interval)
            await self.reconcile()

    async def start(self):
        """Start a service."""
        tasks = await super().start()
        if self.reconciliation_interval > 0:
            self.reconcile_task = self.reconcile_loop()
            tasks.append(self.reconcile_task)
        return tasks

    async def stop(self):
        """Stop a service."""
        super().stop()

    def pre(self, user):
        """Setup function before execution of "OpenConfigChangeHandler"s.
        Args:
            user (dict): Context attributes to provide to "OpenConfigChangeHandler"s.
        """
        sess_running = self.conn.conn.new_session("running")
        sess_operational = self.conn.conn.new_session("operational")
        user["sess"] = {
            "running": sess_running,
            "operational": sess_operational,
        }

    async def post(self, user):
        """Teardown function after execution of "OpenConfigChangeHandler"s.
        If a OpenConfigChangeHandler failed, this will not be called.
        Args:
            user (dict): Context attributes to provide to OpenConfigChangeHandlers.
        """
        try:
            user["sess"]["running"].apply()
            user["sess"]["running"].stop()
            user["sess"]["operational"].stop()
        except Error as e:
            # Just for logging.
            logger.error("Failed to apply changes. %s", e)
            raise e

    # async def _create_objects(self, factory):
    #     required_data = factory.required_data()
    #     src = {}
    #     for d in required_data:
    #         data = self.get_operational_data(d["xpath"], d["default"])
    #         src[d["name"]] = data
    #     return factory.create(src)

    # async def _create_tree(self, subtree):
    #     result = {}
    #     for k, v in subtree.items():
    #         if isinstance(v, dict):
    #             result[k] = await self._create_tree(v)
    #         elif isinstance(v, OpenConfigObjectFactory):
    #             result[k] = await self._create_objects(v)
    #     return result

    # async def oper_cb(self, xpath, priv):
    #     """Callback function to get operational state of the service.
    #     Returns:
    #         dict: Operational states in a tree form.
    #             e.g.
    #             {"interfaces": {"interface": [
    #                 {"name": "Ethernet1/0/1", "state": {"oper-status": "UP"}},
    #                 {"name": "Ethernet1/0/2", "state": {"oper-status": "DOWN"}},
    #             ]}}
    #     """
    #     try:
    #         result = await self._create_tree(self.objects)
    #     except Exception as e:
    #         logger.error("Operational state creation failed. %s", e)
    #         raise e
    #     return result