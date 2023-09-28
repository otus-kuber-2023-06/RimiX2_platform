local kube = import 'vendor/github.com/kube-libsonnet/kube-libsonnet/kube.libsonnet';

local service_stack(name, image) = {
  service_deploy: kube.Deployment(name) {
    spec+: {
      replicas: 1,
      template+: {
        spec+: {
          containers_+: {
            server: kube.Container(name) {
              image: image, 
              name: 'server',
              securityContext: {
                readOnlyRootFilesystem: true,
                runAsNonRoot: true,
                runAsUser: 10001,
              },
              resources: { requests: { cpu: '100m', memory: '64Mi' }, limits: { cpu: '200m', memory: '128Mi' }, },
              env_+: {
                PORT: 50051
              },
              ports_+: { grpc: { containerPort: 50051 } },
              readinessProbe: {
                  initialDelaySeconds: 20,
                  periodSeconds: 15,
                  exec: {
                      command: [
                          "/bin/grpc_health_probe",
                          "-addr=:50051",
                      ],
                  },
              },
              livenessProbe: {
                exec: {
                      command: [
                          "/bin/grpc_health_probe",
                          "-addr=:50051",
                      ],
                },
                initialDelaySeconds: 20,
                periodSeconds: 15,
              },
            },
          },
        },
      },
    },
  },
  service_svc: kube.Service(name) {
    target_pod: $.service_deploy.spec.template,
  }
};

{ ps: service_stack('paymentservice', 'avtandilko/paymentservice:latest'),
ss: service_stack('shippingservice', 'avtandilko/shippingservice:latest')}

// local findObjs(top) = std.flattenArrays([
//   if (std.objectHas(v, "apiVersion") && std.objectHas(v, "kind")) then [v] else findObjs(v)
//   for v in kube.objectValues(top)
// ]);

// kube.List() {
//   items_+: {
//     ps: service_stack('paymentservice', 'avtandilko/paymentservice:latest'), 
//     ss: service_stack('shippingservice', 'avtandilko/shippingservice:latest')
//   },
//   items: findObjs(self.items_),
// }

