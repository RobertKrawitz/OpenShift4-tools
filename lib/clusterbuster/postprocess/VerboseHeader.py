#!/usr/bin/env python3

# Copyright 2022 Robert Krawitz/Red Hat
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

class VerboseHeader:
    def __init__(self, fields: list):
        self.__fields = fields
        self.__n = len(fields)
        self.__last_values = []
        for field in range(self.__n):
            self.__last_values.append(None)

    def print_header(self, row: dict):
        indent_base = '    '
        indent = ''
        for level in range(self.__n):
            if self.__last_values[level] != row[self.__fields[level]]:
                for l1 in range(level, self.__n):
                    self.__last_values[l1] = row[self.__fields[l1]]
                    print(f'{indent}{self.__fields[l1]}: {row[self.__fields[l1]]}')
                    indent += indent_base
                return
            indent += indent_base
