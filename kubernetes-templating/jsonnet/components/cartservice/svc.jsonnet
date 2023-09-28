local kube = import "lib/kube.libsonnet";
local kap = import "lib/kapitan.libjsonnet";
local inventory = kap.inventory();
local p = inventory.parameters;


{
    apiVersion: "v1",
    kind: "Service",
    spec: {
        ports: [
            { name: p.ports.name, port: p.ports.port, targetPort: p.ports.port },
        ],
        selector: { name: p.name },
    },

    metadata: {
        name: p.name,
        labels: { name: p.name },
    },
}