#!/bin/bash -e
{% set i = inventory.parameters %}
DIR=$(dirname ${BASH_SOURCE[0]})

for SECTION in manifests
do
  echo "## run kubectl apply for ${SECTION}"
  kubectl apply -n {{i.namespace}} -f ${DIR}/../${SECTION}/ #--dry-run=client #| column -t
done
