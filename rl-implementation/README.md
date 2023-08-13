## k8s RL autoscaler
k8s RL autoscaler is a project that offers a set of RL environments and RL agents.
The RL environments can be found at the gym-k8s folder while the available agents per RL environment can be found under the agents folder. 
For a detailed view of each environment you can visit the wiki.
A set of RL agents is implemented per environment trying to optimally manage the operation of hpas in terms of elasticity efficiency. The high level objective is to use the smaller number of pod replicas, while satisfying the Service Level Agreements (SLAs) for the operation of the application (throughput, latency or both). The actions regard the selection of proper hpa thresholds for the cpu and memory usage of the deployed pods.

## Install requirementes

`pip3 install -e gym-k8s`

## Kubeless environment setup
The Kubeless environments were tested with the following version for each of the tools:
- `Kubernetes`: 1.19.4 (1.20 doesn't work with Kubeless 1.0.8)
- `Kubeless`: 1.0.8
- `python`: 3.7.10
- `tensorflow`: 2.4.1
- `tf-agents`: 0.7.1

## Licensing

This k8s RL autoscaler component is published under Apache 2.0 license. Please see the LICENSE file for more details.

## Lead Developers

The following lead developers are responsible for this repository and have admin rights.

Eleni Fotopoulou (@efotopoulou)  
Anastasios Zafeiropoulos (@tzafeir)  
Nikos Filinis (@Nickgraviton)  
