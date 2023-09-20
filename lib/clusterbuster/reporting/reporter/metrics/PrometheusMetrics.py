#!/usr/bin/env python3

# Copyright 2022-2023 Robert Krawitz/Red Hat
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
from copy import deepcopy


class PrometheusMetrics:
    """
    Handle Prometheus metrics for ClusterBuster
    """

    def __init__(self, metrics_data: dict, start: float = None, end: float = None):
        """
        Initializer for Prometheus metrics for ClusterBuster
        :param metrics_data: Metrics data from ClusterBuster report
        """
        self._metrics = metrics_data
        self.__start = start
        self.__end = end

    def has_metric(self, metric: str):
        return metric in self._metrics

    def __get_all_matching_metric_data_from_data(self, data: dict, selector: dict = None):
        results = [elt for elt in data]
        if selector:
            for key, desired_value in selector.items():
                new_results = []
                for vector in results:
                    if key in vector['metric']:
                        if isinstance(desired_value, list):
                            if vector['metric'][key] in desired_value:
                                new_results.append(vector)
                        elif isinstance(desired_value, str):
                            if re.search(desired_value, vector['metric'][key]):
                                new_results.append(vector)
                        else:
                            raise TypeError(f'selector element {desired_value} should be list or string')
                results = new_results
                if len(results) == 0:
                    return new_results
        return results

    def __get_all_matching_metric_data(self, metric_name: str, selector: dict = None):
        """
        Retrieve metrics data by name, with optional sub-selection.
        Selectors are a dict of metrics key name and desired target value.
        If the target value is a list, the metrics vectors are searched for
        explicitly matching keys.  If it is a string, the match is done
        by regex.
        :param metric_name: name of desired metric
        :param selector: dictionary of desired values.
        """
        try:
            data = self._metrics[metric_name]['data']
        except KeyError:
            return None
        return self.__get_all_matching_metric_data_from_data(data, selector=selector)

    def __get_unique_matching_metric_data(self, metric_name: str, selector: dict = None):
        """
        Retrieve metrics data by name, with optional sub-selection.
        Selectors are a dict of metrics key name and desired target value.
        If the target value is a list, the metrics vectors are searched for
        explicitly matching keys.  If it is a string, the match is done
        by regex.
        :param metric_name: name of desired metric
        :param selector: dictionary of desired values.
        """
        try:
            data = self._metrics[metric_name]['data']
        except KeyError:
            return None
        answer = self.__get_all_matching_metric_data_from_data(data, selector=selector)
        if len(answer) == 1:
            return self.__get_metric_values(answer[0])
        else:
            raise ValueError(f"Non-unique results for metric {metric_name}, selector {selector}")

    def __get_unique_matching_metric_data_from_data(self, data: dict, selector: dict = None):
        """
        Retrieve metrics data by name, with optional sub-selection.
        Selectors are a dict of metrics key name and desired target value.
        If the target value is a list, the metrics vectors are searched for
        explicitly matching keys.  If it is a string, the match is done
        by regex.
        :param metric_name: name of desired metric
        :param selector: dictionary of desired values.
        """
        answer = self.__get_all_matching_metric_data_from_data(data, selector=selector)
        if len(answer) == 1:
            return self.__get_metric_values(answer[0])
        elif len(answer) == 0:
            return {}
        else:
            raise ValueError(f"Non-unique results for metric, selector {selector}")

    def __get_metric_keys(self, metrics_results: dict, key: str):
        """
        Retrieve the list of named values for the specified key
        :param metrics_results: metrics results returned from get_metrics_data
        :param key: name of the key
        :return: list of names
        """
        if not isinstance(metrics_results, list):
            raise TypeError("get_metric_keys should be called on a list")
        answer = {}
        for elt in metrics_results:
            answer[self.__get_metric_key(elt, key)] = 1
        return sorted(answer.keys())

    def __get_metric_key(self, metrics_results: dict, key: str):
        """
        Retrieve the value of a key for the specified metrics result
        :param metrics_results: one element of metrics results returned from get_metrics_data
        :param key: name of the key
        :return: name
        """
        try:
            metric = metrics_results['metric']
        except KeyError:
            raise TypeError("metrics_results does not appear to be a valid metrics result")
        # This isn't the same case; we have something that looks valid, but
        # doesn't have what we want.
        try:
            return metric[key]
        except KeyError:
            raise KeyError(f"No value for '{key}' in metrics metadata")

    def __safe_convert_to_float(self, result: str):
        """
        Safely convert a raw result to a float
        :param result: result to be converted
        """
        try:
            return float(result)
        except ValueError:
            return result

    def __get_metric_values(self, metrics_results: dict):
        """
        Retrieve the raw metrics value or value vector from the specified result.
        :param metrics_results: one element of metrics results returned from __get_metrics_data
        """
        if 'value' in metrics_results:
            raw_results = [metrics_results['value']]
        elif 'values' in metrics_results:
            raw_results = metrics_results['values']
        else:
            raise TypeError("metrics_results does not appear to be a valid metrics result")
        return [[elt[0], self.__safe_convert_to_float(elt[1])] for elt in raw_results]

    def __filter_metrics_by_time(self, mode: str, values: list, start: float = -1, end: float = -1):
        if start is not None and start < 0:
            start = self.__start
        if end is not None and end < 0:
            end = self.__end

        if start is None and end is None:
            return values
        answer = []
        if mode != 'value' and mode != 'rate':
            raise ValueError(f"Illegal filter mode '{mode}', must be either 'rate' or 'value'")
        if mode == 'value' or start is None:
            for value in values:
                if (start is None or value[0] >= start) and (end is None or value[0] <= end):
                    answer.append(value)
        else:
            for i in range(1, len(values) - 1):
                prev = answer[i - 1]
                cur = answer[i]
                if prev[0] >= start and cur[0] <= end:
                    answer.append(cur)
        return answer

    def __find_metric_value_by_time(self, values: list, time: float):
        if time < values[0][0] or time > values[len(values) - 1][0]:
            return None
        else:
            for i in range(1, len(values) - 1):
                prev = values[i - 1]
                cur = values[i]
                if prev[0] <= time and cur[0] > time:
                    return prev[1]
            return cur[1]

    def __get_max_value(self, values: list, start: float = -1, end: float = -1):
        """
        Retrieve the maximum value and the specified value vector.
        :param values: values vector
        """
        values = self.__filter_metrics_by_time('value', values)
        answer = None
        for value in values:
            if not answer or value[1] > answer:
                answer = value[1]
        return answer

    def __get_max_rate(self, values: list, start: float = -1, end: float = -1):
        """
        Retrieve the maximum rate (per second) and corresponding interval
        from the specified value vector.
        :param values: values vector
        """
        values = self.__filter_metrics_by_time('rate', values)
        answer = None
        if len(values) > 2:
            for i in range(1, len(values) - 1):
                rate = (values[i][1] - values[i - 1][1]) / (values[i][0] - values[i - 1][0])
                if answer is None or rate > answer:
                    answer = rate
        return answer

    def __get_avg_value(self, values: list, start: float = -1, end: float = -1):
        """
        Retrieve the average value and the specified value vector.
        :param values: values vector
        """
        values = self.__filter_metrics_by_time('value', values)
        if len(values) > 0:
            answer = 0
            for value in values:
                answer += value[1]
            return answer / len(values)
        return None

    def __get_avg_rate(self, values: list, start: float = -1, end: float = -1):
        """
        Retrieve the average rate (per second) and corresponding interval
        from the specified value vector.
        :param values: values vector
        """
        values = self.__filter_metrics_by_time('rate', values)
        if len(values) > 1:
            return (values[len(values) - 1][1] - values[0][1]) / (values[len(values) - 1][0] - values[0][0])
        return None

    def __build_metrics_tree(self, keys: list, data: dict, path: dict, op: str, printfunc=None, start: float = -1, end: float = -1):
        answer = {}
        nkeys = deepcopy(keys)
        mykey = nkeys.pop()
        metrics_keys = self.__get_metric_keys(data, mykey)
        for subkey in metrics_keys:
            if len(nkeys) > 0:
                answer[f'{mykey}: {subkey}'] = self.__build_metrics_tree(keys=nkeys, data=data,
                                                                         path={**path, mykey: [subkey]}, op=op,
                                                                         printfunc=printfunc)
            else:
                metrics_data = self.__get_unique_matching_metric_data_from_data(data, selector={**path, mykey: [subkey]})
                if op == 'max_rate':
                    answer[f'{mykey}: {subkey}'] = self.__get_max_rate(metrics_data)
                elif op == 'max_value':
                    answer[f'{mykey}: {subkey}'] = self.__get_max_value(metrics_data)
                elif op == 'avg_rate':
                    answer[f'{mykey}: {subkey}'] = self.__get_avg_rate(metrics_data)
                elif op == 'avg_value':
                    answer[f'{mykey}: {subkey}'] = self.__get_avg_value(metrics_data)
                if printfunc:
                    answer[f'{mykey}: {subkey}'] = printfunc(answer[f'{mykey}: {subkey}'])
        return answer

    def __get_op_by_key(self, op: str, metric_name: str, selector: dict = None, printfunc=None, start: float = -1, end: float = -1):
        metrics = self.__get_all_matching_metric_data(metric_name, selector=selector)
        if metrics:
            keys = sorted(metrics[0]['metric'].keys())
            return self.__build_metrics_tree(keys, metrics, {}, op, printfunc)

    def get_max_value_by_key(self, metric_name: str, selector: dict = None, printfunc=None, start: float = -1, end: float = -1):
        return self.__get_op_by_key('max_value', metric_name, selector, printfunc)

    def get_max_rate_by_key(self, metric_name: str, selector: dict = None, printfunc=None, start: float = -1, end: float = -1):
        return self.__get_op_by_key('max_rate', metric_name, selector, printfunc)

    def get_avg_value_by_key(self, metric_name: str, selector: dict = None, printfunc=None, start: float = -1, end: float = -1):
        return self.__get_op_by_key('avg_value', metric_name, selector, printfunc)

    def get_avg_rate_by_key(self, metric_name: str, selector: dict = None, printfunc=None, start: float = -1, end: float = -1):
        return self.__get_op_by_key('avg_rate', metric_name, selector, printfunc)

    def __build_metrics_value_tree(self, time: float, keys: list, data: dict, path: dict):
        answer = {}
        nkeys = deepcopy(keys)
        mykey = nkeys.pop()
        metrics_keys = self.__get_metric_keys(data, mykey)
        for subkey in metrics_keys:
            if len(nkeys) > 0:
                answer[subkey] = self.__build_metrics_value_tree(time=time, keys=nkeys, data=data,
                                                                 path={**path, mykey: [subkey]})
            else:
                metrics_data = self.__get_unique_matching_metric_data_from_data(data, selector={**path, mykey: [subkey]})
                return self.__find_metric_value_by_time(metrics_data, time)
        return answer

    def get_value_by_key(self, metric_name: str, time: float, selector: dict = None):
        metrics = self.__get_all_matching_metric_data(metric_name, selector=selector)
        if self.__start is not None:
            time += self.__start
        if metrics:
            keys = sorted(metrics[0]['metric'].keys())
            return self.__build_metrics_value_tree(time, keys, metrics, selector)
