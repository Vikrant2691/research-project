import datetime
import math
import random
import time
from pprint import pprint

import numpy as np
import requests
from gym import spaces, Env
from kubernetes import client, config

class K8sEnvContinuousStateDiscreteActionV0(Env):
    metadata = {
        'render.modes': ['human']
    }

    def __init__(self, timestep_duration, app_name, sla_latency, sla_throughput,
            prometheus_host, prometheus_latency_metric_name,
            prometheus_requests_metric_name, prometheus_denied_requests_metric_name,
            cpu_thresh_init, memory_thresh_init):

        config.load_kube_config()

        self.done = False
        self.MAX_PODS = 10
        self.MIN_PODS = 1
        self.threshold_step = 20
        self.cpu_thresh_init = cpu_thresh_init
        self.memory_thresh_init = memory_thresh_init
        self.timestep_duration = timestep_duration
        self.app_name = app_name
        self.sla_latency = float(sla_latency)
        self.sla_throughput = float(sla_throughput)
        self.prometheus_host = prometheus_host
        self.prometheus_latency_metric_name = prometheus_latency_metric_name
        self.prometheus_requests_metric_name = prometheus_requests_metric_name
        self.prometheus_denied_requests_metric_name = prometheus_denied_requests_metric_name

        # Observation:
        # [pod_cpu, cpu_hpa_threshold, pod_memory, memory_hpa_threshold, pod_number,
        #  pods_backoff, pod_throughput_level, pod_throughput_rate, pod_latency]
        self.observation_space = spaces.Box(
            np.array([0, 0, 0, 0, 1,
                0, 0, 0, 0]),
            np.array([200, 100, 200, 100, self.MAX_PODS,
                self.MAX_PODS, 100 * self.sla_throughput, 1, 100 * self.sla_latency]),
            dtype=np.float64
        )
        # Possible actions for CPU x Memory thresholds:
        self.action_space = spaces.Discrete(9)
        self.reward_range = (0, 100)

    def step(self, action):
        """
        Returns
        -------
        observation, reward, done, dt_dict : tuple
            observation: list
                list of observations
            reward : float
                amount of reward achieved by the previous action. The scale
                varies between environments, but the goal is always to increase
                your total reward.
            done : boolean
                boolean value of whether training is done or not. Becomes True
                when errors occur.
            dt_dict : Dict
                dictionary of formatted date and time.
        """
        self._take_action(action)  # Create HPA
        wait_time = self.timestep_duration * 60
        time.sleep(wait_time)  # Wait timestep_duration minutes for the changes to take place

        observation = self._get_state()
        reward = self._get_reward(observation)

        now = datetime.datetime.now()
        dt_string = now.strftime('%d/%m/%Y %H:%M:%S')
        dt_dict = {
            'datetime': dt_string
        }

        return observation, reward, self.done, dt_dict

    def reset(self):
        min_threshold = 20
        max_threshold = 100
        possible_thresholds = list(
            range(min_threshold, max_threshold + 1, self.threshold_step)
        )

        if self.cpu_thresh_init in possible_thresholds:
            cpu_threshold = self.cpu_thresh_init
        else:
            cpu_threshold = random.choice(possible_thresholds)

        if self.memory_thresh_init in possible_thresholds:
            memory_threshold = self.memory_thresh_init
        else:
            memory_threshold = random.choice(possible_thresholds)

        self._create_hpa(cpu_threshold, memory_threshold)
        return self._get_state()

    def render(self, mode='human'):
        return None

    def close(self):
        pass

    def _take_action(self, action):
        (cpu_threshold_action,
         memory_threshold_action) = self._decode_action(action)

        # Do nothing
        if cpu_threshold_action == 1 and memory_threshold_action == 1:
            return

        (hpa_error,
         pod_cpu_current_util,
         pod_cpu_threshold,
         pod_memory_current_util,
         pod_memory_threshold,
         current_replicas) = self._get_existing_app_hpa()

        if hpa_error == 1:
            self.done = True
        else:
            self.done = False

        if pod_cpu_threshold != 0 and pod_memory_threshold != 0:
            # Delete the hpa
            v2 = client.AutoscalingV2beta2Api()
            api_response = v2.delete_namespaced_horizontal_pod_autoscaler(
                name=self.app_name, namespace='default', pretty='true'
            )

        # Adjust the threshold
        new_cpu_hpa_threshold = pod_cpu_threshold

        if cpu_threshold_action == 0 and pod_cpu_threshold > 20:
            new_cpu_hpa_threshold -= self.threshold_step

        if cpu_threshold_action == 2 and pod_cpu_threshold < 100:
            new_cpu_hpa_threshold += self.threshold_step

        new_memory_hpa_threshold = pod_memory_threshold

        if memory_threshold_action == 0 and pod_memory_threshold > 20:
            new_memory_hpa_threshold -= self.threshold_step

        if memory_threshold_action == 2 and pod_memory_threshold < 100:
            new_memory_hpa_threshold += self.threshold_step

        self._create_hpa(new_cpu_hpa_threshold, new_memory_hpa_threshold)
       
    def _get_state(self):
        # Get metrics from metrics-server API
        (hpa_error,
         pod_cpu_current_util,
         pod_cpu_threshold,
         pod_memory_current_util,
         pod_memory_threshold,
         current_replicas) = self._get_existing_app_hpa()

        v1 = client.CoreV1Api()
        events_list = v1.list_event_for_all_namespaces()
        pods_backoff = 0
        for event in events_list.items:
          if self.app_name in event.metadata.name and event.reason == 'BackOff':
              pods_backoff += int(event.count)

        # Get latency
        latency = self._query_prometheus(self.prometheus_latency_metric_name)
        if math.isnan(latency):
            latency = 1000

        # Get throughput
        total_requests = self._query_prometheus(self.prometheus_requests_metric_name)

        throughput_level = 0
        throughput_rate = 1       
        if total_requests > 0:
            denied_requests = self._query_prometheus(self.prometheus_denied_requests_metric_name)
            if math.isnan(denied_requests):
                denied_requests = 0

            throughput_level = total_requests - denied_requests
            throughput_rate = throughput_level / total_requests

        observation = [
            pod_cpu_current_util,
            pod_cpu_threshold,
            pod_memory_current_util,
            pod_memory_threshold,
            current_replicas,
            pods_backoff,
            latency,
            throughput_level,
            throughput_rate
        ]

        return observation

    def _get_reward(self, observation):
        """
        Calculate reward value: The environment receives the current values of
        pod_number and cpu/memory metric values that correspond to the current
        state of the system s. The reward value r is calculated based on two
        criteria:
        (i)  the amount of resources acquired,
             which directly determines the cost
        (ii) the number of pods needed to support the received load.
        """

        (pod_cpu_current_util,
         pod_cpu_threshold,
         pod_memory_current_util,
         pod_memory_threshold,
         pod_number,
         pods_backoff,
         latency,
         throughput_level,
         throughput_rate) = observation

        reward_min = 0
        reward_max = 100
        reward = 0

        pod_weight = 0.2
        latency_weight = 0.4
        throughput_weight = 0.4

        d = 5.0  # this is a hyperparameter of the reward function

        latency_ratio = latency / self.sla_latency
        throughput_ratio = throughput_level / self.sla_throughput

        # Best case scenario
        if pod_number == 1 and latency_ratio <= 1\
                and throughput_ratio <= 2 and throughput_rate >= 0.95:
            return reward_max
        # Worst case scenario
        if latency_ratio > 1:
            return reward_min

        # Pod reward
        pod_reward = -100 / (self.MAX_PODS - 1) * pod_number \
            + 100 * self.MAX_PODS / (self.MAX_PODS - 1)
        reward += pod_weight * pod_reward

        # Latency reward
        latency_ref_value = 0.8
        if latency_ratio < latency_ref_value:
            latency_reward = 100 * pow(math.e, -0.3 * d * pow(latency_ref_value - latency_ratio, 2))
        else:
            latency_reward = 100 * pow(math.e, -10 * d * pow(latency_ref_value - latency_ratio, 2))
        reward += latency_weight * latency_reward

        # Throughput reward
        throughput_ref_value = 2
        if throughput_rate >= 0.95 and throughput_ratio < throughput_ref_value:
            throughput_reward = 100 * pow(math.e, -0.05 * d * pow(throughput_ref_value - throughput_ratio, 2))
        else:
            throughput_reward = 100 * pow(math.e, -10 * d * pow(throughput_ref_value - throughput_ratio, 2))
        reward += throughput_weight * throughput_reward

        return reward

    def _get_existing_app_hpa(self):
        hpa_error = 0
        pod_cpu_current_util = 0
        pod_cpu_threshold = 0
        pod_memory_current_util = 0
        pod_memory_threshold = 0
        current_replicas = self.MAX_PODS

        # See if there are any existing HPA
        v2 = client.AutoscalingV2beta2Api()
        name = self.app_name
        namespace = 'default'
        pretty = 'true'

        try:
            item = v2.read_namespaced_horizontal_pod_autoscaler(
                name, namespace, pretty=pretty
            )
            if item.metadata.name == self.app_name:
                for metric in item.status.current_metrics:
                    if metric.resource.name == 'cpu':
                        pod_cpu_current_util = metric.resource.current.average_utilization
                    if metric.resource.name == 'memory':
                        pod_memory_current_util = metric.resource.current.average_utilization

                for condition in item.status.conditions:
                    if condition.reason != 'DesiredWithinRange' and condition.status == 'False':
                        hpa_error = 1
                        return [
                            hpa_error, pod_cpu_current_util, pod_cpu_threshold,
                            pod_memory_current_util, pod_memory_threshold, current_replicas
                        ]

                metrics = item.spec.metrics
                for metric in metrics:
                    if metric.resource.name == 'cpu':
                        pod_cpu_threshold = metric.resource.target.average_utilization
                    if metric.resource.name == 'memory':
                        pod_memory_threshold = metric.resource.target.average_utilization

                current_replicas = item.status.current_replicas
                return [
                    hpa_error, pod_cpu_current_util, pod_cpu_threshold,
                    pod_memory_current_util, pod_memory_threshold, current_replicas
                ]
        except Exception:
                return [
                    hpa_error, pod_cpu_current_util, pod_cpu_threshold,
                    pod_memory_current_util, pod_memory_threshold, current_replicas
                ]

    def _create_hpa(self, cpu_threshold, memory_threshold):
        v2 = client.AutoscalingV2beta2Api()

        my_metrics = []
        if cpu_threshold != 0:
            my_metrics.append(
                client.V2beta2MetricSpec(
                    type='Resource', resource=client.V2beta2ResourceMetricSource(
                        name='cpu', target=client.V2beta2MetricTarget(
                            average_utilization=cpu_threshold, type='Utilization')
                    )
                )
            )
        if memory_threshold != 0:
            my_metrics.append(
                client.V2beta2MetricSpec(
                    type='Resource', resource=client.V2beta2ResourceMetricSource(
                        name='memory', target=client.V2beta2MetricTarget(
                            average_utilization=memory_threshold, type='Utilization')
                    )
                )
            )


        if len(my_metrics) > 0:
            my_conditions = []
            my_conditions.append(client.V2beta2HorizontalPodAutoscalerCondition(
                status='True', type='AbleToScale')
            )

            status = client.V2beta2HorizontalPodAutoscalerStatus(
                conditions=my_conditions, current_replicas=1, desired_replicas=1
            )

            body = client.V2beta2HorizontalPodAutoscaler(
                api_version='autoscaling/v2beta2',
                kind='HorizontalPodAutoscaler',
                metadata=client.V1ObjectMeta(name=self.app_name),
                spec=client.V2beta2HorizontalPodAutoscalerSpec(
                    max_replicas=self.MAX_PODS,
                    min_replicas=self.MIN_PODS,
                    metrics=my_metrics,
                    scale_target_ref=client.V2beta2CrossVersionObjectReference(
                        kind='Deployment', name=self.app_name, api_version='apps/v1'
                    ),
                ),
                status=status
            )

            try:
                api_response = v2.create_namespaced_horizontal_pod_autoscaler(
                    namespace='default', body=body, pretty=True
                )
                pprint(api_response)
            except Exception as e:
                print('Created new namespaced_horizontal_pod_autoscaler')

    def _query_prometheus(self, query_name):
        prometheus_endpoint = '{}/api/v1/query'.format(self.prometheus_host)
        response = requests.get(
            prometheus_endpoint, params={
                'query': query_name
            }
        )

        results = response.json()['data']['result']
        if len(results) > 0:
            return float(results[0]['value'][1])
        else:
            return float('NaN')

    def _decode_action(self, action):
        cpu_threshold_action = action // 3
        memory_threshold_action = action % 3
        return [cpu_threshold_action, memory_threshold_action]
