#!/usr/bin/env bash

set -ex

echo "CHAOS testing: setting up..."

# Install deps.
sudo dnf install -y curl openssl python36 python39

# Install helm.
if [[ -z "$(command -v helm)" ]]; then
    curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
    chmod 700 get_helm.sh
    ./get_helm.sh
fi

# Install consumer addon.
make install PY_BIN=python3.9
make install-consumer-addon

# Install ocs-monkey.
if [[ ! -d ocs-monkey ]]; then
    git clone --depth=1 --no-tags https://github.com/red-hat-storage/ocs-monkey
fi
cd ocs-monkey
python3.6 -m venv venv  # @TODO: modify setup-env.sh to allow choosing python version and venv dir name.
source setup-env.sh

# Start workload runner.
export CONSUMER_KUBECONFIG=../.cluster/consumer-kubeconfig.yaml
KUBECONFIG="${CONSUMER_KUBECONFIG}" helm install workload ./helm/ocs-monkey-generator \
     --set workload.runtime=9000

# Start chaos runner.
export PROVIDER_KUBECONFIG=../.cluster/provider-kubeconfig.yaml
KUBECONFIG="${PROVIDER_KUBECONFIG}" ./chaos_runner.py -t 7200 --monitor-deployment default/workload-ocs-monkey-generator \
    --monitor-deployment-cluster-config "${CONSUMER_KUBECONFIG}"

# Clean up after a successful run.
deactivate || true
cd -
make cleanup

echo "CHAOS testing completed."
