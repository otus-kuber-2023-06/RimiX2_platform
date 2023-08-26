{
  local k = (import "vendor/github.com/jsonnet-libs/k8s-libsonnet/1.26/main.libsonnet"),
  foo: k.apps.v1.deployment.new(name="foo", containers=[
    k.core.v1.container.new(name="foo", image="foo/bar")
  ])
}
