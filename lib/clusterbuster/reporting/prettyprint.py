#!/usr/bin/env python3
# Copyright 2023 Robert Krawitz/Red Hat
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


def fformat(num: float, precision: int = 5):
    """
    Return a rounded representation of a number.
    :param num:
    :param precision:
    """
    try:
        if precision > 1:
            return f'{num:.{precision}f}'
        else:
            return str(round(num))
    except TypeError:
        return str(num)


def prettyprint(num: float, precision: int = 5, integer: int = 0, base: int = None,
                suffix: str = '', multiplier: float = 1, parseable: bool = False):
    """
    Return a pretty printed version of a number.
    Base 100:  print percent
    Base 1000: print with decimal units (1000, 1000000...)
    Base 1024: print with binary units (1024, 1048576...)
               This only applies to values larger than 1;
               smaller values are always printed with
               decimal units
    Base 0:    do not use any units
    Base -1:   Only print units for <1
    :param num:
    :param precision:
    :param base: 0, 100, 1000 (default), 1024, or -1
    :param integer: print as integer
    :param suffix: trailing suffix (e. g. "B/sec")
    :param multiplier: number to multiply input by.
    :param parseable: print result in a parseable format
    """
    if num is None:
        return 'None'
    if base is None:
        base = 1000
    try:
        num = float(num)
    except ValueError:
        return str(num)
    num *= multiplier
    if integer or num == 0:
        return str(int(num))
    if parseable:
        if base == 100:
            precision += 2
        elif abs(float(num)) < .000001:
            precision += 9
        elif abs(float(num)) < .001:
            precision += 6
        elif abs(float(num)) < 1:
            precision += 3
        return fformat(num, precision=precision)
    elif base == 0:
        if suffix and suffix != '':
            return f'{fformat(num, precision=precision)} {suffix}'
        else:
            return f'{fformat(num, precision=precision)}'
    elif base == 100:
        return f'{fformat(num * 100, precision=precision)} %'
    elif base == 1000 or base == 10:
        infix = ''
        base = 1000
    elif base == 1024 or base == 2:
        infix = 'i'
        base = 1024
    elif base != -10 or base != -1 or base != -1000:
        raise ValueError(f'Illegal base {base} for prettyprint; must be 1000 or 1024')
    if base > 0 and abs(num) >= base ** 5:
        return f'{fformat(num / (base ** 5), precision=precision)} P{infix}{suffix}'
    elif base > 0 and abs(num) >= base ** 4:
        return f'{fformat(num / (base ** 4), precision=precision)} T{infix}{suffix}'
    elif base > 0 and abs(num) >= base ** 3:
        return f'{fformat(num / (base ** 3), precision=precision)} G{infix}{suffix}'
    elif base > 0 and abs(num) >= base ** 2:
        return f'{fformat(num / (base ** 2), precision=precision)} M{infix}{suffix}'
    elif base > 0 and abs(num) >= base ** 1:
        return f'{fformat(num / base, precision=precision)} K{infix}{suffix}'
    elif abs(num) >= 1 or num == 0:
        if integer:
            precision = 0
        return f'{fformat(num, precision=precision)} {suffix}'
    elif abs(num) >= 10 ** -3:
        return f'{fformat(num * (1000), precision=precision)} m{suffix}'
    elif abs(num) >= 10 ** -6:
        return f'{fformat(num * (1000 ** 2), precision=precision)} u{suffix}'
    elif abs(num) >= 10 ** -9:
        return f'{fformat(num * (1000 ** 3), precision=precision)} n{suffix}'
    else:
        return f'{fformat(num * (1000 ** 4), precision=precision)} p{suffix}'
