local kap = import "lib/kapitan.libjsonnet";
local deployment = import "./deploy.jsonnet";
local service = import "./svc.jsonnet";
local inventory = kap.inventory();
local p = inventory.parameters;


{
    "deployment": deployment,
    "service": service,
}
