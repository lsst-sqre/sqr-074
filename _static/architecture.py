"""Source for architecture.png component diagram."""

import os

from diagrams import Cluster, Diagram, Edge
from diagrams.gcp.compute import KubernetesEngine
from diagrams.onprem.client import Client, User

os.chdir(os.path.dirname(__file__))

graph_attr = {
    "label": "",
    "labelloc": "bbc",
    "nodesep": "0.2",
    "pad": "0.2",
    "ranksep": "0.75",
    "splines": "splines",
}

node_attr = {
    "fontsize": "12.0",
}

with Diagram(
    "Phalanx validation",
    show=False,
    filename="architecture",
    outformat="png",
    graph_attr=graph_attr,
    node_attr=node_attr,
):
    user = User("End user")
    installer = Client("Installer")

    with Cluster("Phalanx"):
        gafaelfawr = KubernetesEngine("Gafaelfawr")
        muster = KubernetesEngine("Muster")
        mobu = KubernetesEngine("mobu")

    (
        user
        >> Edge(label="ingress")
        >> muster
        >> Edge(label="ingress")
        >> gafaelfawr
    )
    (
        installer
        >> Edge(label="ingress")
        >> mobu
        >> Edge(label="ingress")
        >> muster
    )
