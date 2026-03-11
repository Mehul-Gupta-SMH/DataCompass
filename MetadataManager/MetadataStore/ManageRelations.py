from .relationdb import networkxDB

class Relations:
    """
    A class for managing relations using various storage types.

    attr:
        - strgType (str): Type of storage used for relations.
        - GraphObj: Graph object for storing relations.
    """

    def __init__(self, strgType = "networkx", instance_name: str = "default"):
        """
        Initialize the Relations object.

        args:
            - strgType (str): Storage type. Currently only "networkx" is supported.
            - instance_name (str): Named database instance (e.g. "default", "snowflake_prod").
        """
        self.strgType = strgType
        self.instance_name = instance_name
        self.GraphObj = None

    def __instGraphObj__(self):
        """
        Initialize the graph object based on the storage type.
        """
        if self.strgType == "networkx":
            self.GraphObj = networkxDB.getObj(self.instance_name)

    def addRelation(self, edges, instance_name: str = None):
        """
        Add relations to the graph object.

        args:
            - edges (dict): Dictionary containing edge tuples as keys (source, target) and edge attributes as values.
            - instance_name (str): Override instance name for this call. Falls back to self.instance_name.
        """
        self.__instGraphObj__()
        iname = instance_name if instance_name is not None else self.instance_name

        if self.strgType == "networkx":
            networkxDB.addRelations(self.GraphObj, edges, iname)


    def getRelation(self, target_nodes = [], instance_name: str = None):
        """
        Retrieve relations from the graph object.

        args:
            - target_nodes (list): List of target nodes to retrieve relations for.
            - instance_name (str): Ignored (instance already set at construction). Kept for API symmetry.

        returns:
            - dict: Dictionary containing retrieved relations.
        """
        self.__instGraphObj__()

        if self.strgType == "networkx":
            return networkxDB.getRelations(self.GraphObj, target_nodes)


    def visRelations(self):
        self.__instGraphObj__()

        if self.strgType == "networkx":
            networkxDB.visualizeRelations(self.GraphObj)

            return "Refreshed relations map"
