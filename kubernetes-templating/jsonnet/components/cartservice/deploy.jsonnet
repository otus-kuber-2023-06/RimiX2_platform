local kube = import "lib/kube.libsonnet";
local kap = import "lib/kapitan.libjsonnet";
local inventory = kap.inventory();
local p = inventory.parameters;
 
local deployment(p) = kube.Deployment(p.name) {
    spec+: {
      replicas: 1,
      template+: {
        spec+: {
          containers_+: {
            server: kube.Container(p.name) {
              image: p.image, 
              name: 'server',
              resources: { requests: { cpu: '200m', memory: '64Mi' }, limits: { cpu: '300m', memory: '128Mi' }, },
              env_+: {
                PORT: p.ports.port,
                REDIS_ADDR: "hipster-shop-redis-master:6379",
                LISTEN_ADDR: "0.0.0.0"
              },
              ports_+: { grpc: { containerPort: p.ports.port } },
              readinessProbe: {
                  initialDelaySeconds: 15,
                  exec: {
                      command: ["/bin/grpc_health_probe", "-addr=:"+p.ports.port, "-rpc-timeout=5s"
                      ],
                  },
              },
              livenessProbe: {
                exec: {
                      command: ["/bin/grpc_health_probe", "-addr=:"+p.ports.port, "-rpc-timeout=5s"
                      ],
                },
                initialDelaySeconds: 15,
                periodSeconds: 10,
              },
            },
          },
        },
      },
    },
};

deployment(p)