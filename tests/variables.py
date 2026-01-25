

class REMOTES:
    class central:
        ssh = "central"
        zenohd_config = "~/raspberrypi_zenoh_redundant_mesh/zenoh_config/router.json5"
    class node1:
        ssh = "node1"
        zenohd_config = "~/raspberrypi_zenoh_redundant_mesh/zenoh_config/node_router.json5"
    class node2:
        ssh = "node2"
        zenohd_config = "~/raspberrypi_zenoh_redundant_mesh/zenoh_config/node_router.json5"

class SSHTargets:
    router = REMOTES.central.ssh
    node1 = REMOTES.node1.ssh
    node2 = REMOTES.node2.ssh

