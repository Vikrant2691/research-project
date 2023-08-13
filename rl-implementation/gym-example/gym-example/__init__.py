from gym.envs.registration import register

register(
    id='k8s-with-performance-metric-v0',
    entry_point='gym_k8s.envs:K8sEnvWithPerformanceMetric',
)


register(
    id='k8s-env-discrete-state-discrete-action-v0',
    entry_point='gym_k8s.envs:K8sEnvDiscreteStateDiscreteActionV0',
)

register(
    id='k8s-env-discrete-state-discrete-action-v1',
    entry_point='gym_k8s.envs:K8sEnvDiscreteStateDiscreteActionV1',
)

register(
    id='k8s-env-discrete-state-discrete-action-v2',
    entry_point='gym_k8s.envs:K8sEnvDiscreteStateDiscreteActionV2',
)

register(
    id='k8s-env-discrete-state-discrete-action-v3',
    entry_point='gym_k8s.envs:K8sEnvDiscreteStateDiscreteActionV3',
)

register(
    id='k8s-env-discrete-state-discrete-action-v4',
    entry_point='gym_k8s.envs:K8sEnvDiscreteStateDiscreteActionV4',
)

register(
    id='k8s-env-discrete-state-discrete-action-v5',
    entry_point='gym_k8s.envs:K8sEnvDiscreteStateDiscreteActionV5',
)

register(
    id='k8s-env-discrete-state-discrete-action-v6',
    entry_point='gym_k8s.envs:K8sEnvDiscreteStateDiscreteActionV6',
)

register(
    id='k8s-env-continuous-state-discrete-action-v0',
    entry_point='gym_k8s.envs:K8sEnvContinuousStateDiscreteActionV0',
)

register(
    id='k8s-env-continuous-state-discrete-action-v1',
    entry_point='gym_k8s.envs:K8sEnvContinuousStateDiscreteActionV1',
)
