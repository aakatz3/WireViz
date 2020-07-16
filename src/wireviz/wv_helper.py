#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from decimal import Decimal, ROUND_HALF_UP
from typing import List
from math import pi, pow, log, sqrt
import re

# No need for common AWG list, its just [4-1]/0, 1-3, and evens >=4
# Alternative inputs for AWG, that some people may use
uncommon_awg = {
    '0000': '4/0',
    '000': '3/0',
    '00': '2/0',
    '0': '1/0'
}

# In the US, sizes larger than AWG0000 / AWG 4/0 are usually in kcmil (aka MCM)
# Presently, these are unimplemented, but are available for future use
common_kcmil = [250, 300, 350, 400, 500, 600, 700, 750, 750, 800, 900, 1000, 1250, 1500, 1750, 2000]

# Common sizes from https://docs.rs-online.com/37cc/0900766b815c9b65.pdf and from IEC 60228
#common_mm2 = ['0.22', '0.23', '0.34', '0.5', '0.75', '1', '1.5', '2.5', '4', '6', '10', '16', '25', '35', '50', '70', '95', '120', '150', '185', '240', '300', '400', '500', '630', '800', '1000', '1200', '1400', '1600', '1800', '2000', '2500'] #
common_mm2 = [0.22, 0.23, 0.34, 0.5, 0.75, 1, 1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240, 300, 400, 500, 630, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2500]

# Strict mode restricts odd awg bigger than 4
def awg_equiv(mm2, strict='yes'):
    strict = strict.lower()
    if strict != 'yes' and strict != 'no':
        raise ValueError
    try:
        mm2 = int(re.findall(r'\d+',mm2)[0])
    except ValueError:
        return 'Unknown (' + mm2 + ')'
    d = 2 * sqrt(mm2 / pi)
    awg = 36 - (39 * log(d/0.127,92))
    if awg > 0:
        # We want to round to whatever is closest, not round to even
        if strict=='yes' and awg > 3:
            awg = int(Decimal(awg/2.).quantize(0, ROUND_HALF_UP)*2)
        else:
            awg = int(Decimal(awg).quantize(0, ROUND_HALF_UP))
    # After rounding, it is possible that AWG is now 0
    if awg <= 0:
        return str(1-int(awg)) + '/0'
    else:
        return str(awg)

# Strict mode restricts allowed square mm value to the common sizes
def mm2_equiv(awg, strict='yes'):
    strict = strict.lower()
    if awg in uncommon_awg:
        awg = uncommon_awg[awg]
    if '/' in awg:
        n = 1 - int(awg[awg.find('/')])
    else:
        try:
            n = int(re.findall(r'\d+',awg)[0])
        except ValueError:
            return 'Unknown (' + awg + ')'
    d_mm = 0.127 * pow(92,((36-n)/39))
    mm2 = round(pi * pow((d_mm / 2.0), 2),2)
    if strict == 'yes':
        return closest(common_mm2, mm2)
    elif strict == 'no':
        return str(mm2)
    else:
         raise NotImplementedError

# https://www.geeksforgeeks.org/python-find-closest-number-to-k-in-given-list/
def closest(lst, K):
    return lst[min(range(len(lst)), key=lambda i: abs(lst[i] - K))]

def nested_html_table(rows):
    # input: list, each item may be scalar or list
    # output: a parent table with one child table per parent item that is list, and one cell per parent item that is scalar
    # purpose: create the appearance of one table, where cell widths are independent between rows
    html = '<table border="0" cellspacing="0" cellpadding="0">'
    for row in rows:
        if isinstance(row, List):
            if len(row) > 0 and any(row):
                html = f'{html}<tr><td><table border="0" cellspacing="0" cellpadding="3" cellborder="1"><tr>'
                for cell in row:
                    if cell is not None:
                        html = f'{html}<td balign="left">{cell}</td>'
                html = f'{html}</tr></table></td></tr>'
        elif row is not None:
            html = f'{html}<tr><td>{row}</td></tr>'
    html = f'{html}</table>'
    return html


def expand(yaml_data):
    # yaml_data can be:
    # - a singleton (normally str or int)
    # - a list of str or int
    # if str is of the format '#-#', it is treated as a range (inclusive) and expanded
    output = []
    if not isinstance(yaml_data, list):
        yaml_data = [yaml_data]
    for e in yaml_data:
        e = str(e)
        if '-' in e:  # list of pins
            a, b = tuple(map(int, e.split('-')))
            if a < b:
                for x in range(a, b + 1):
                    output.append(x)
            elif a > b:
                for x in range(a, b - 1, -1):
                    output.append(x)
            elif a == b:
                output.append(a)
        else:
            try:
                x = int(e)
            except Exception:
                x = e
            output.append(x)
    return output


def int2tuple(inp):
    if isinstance(inp, tuple):
        output = inp
    else:
        output = (inp,)
    return output


def flatten2d(inp):
    return [[str(item) if not isinstance(item, List) else ', '.join(item) for item in row] for row in inp]


def tuplelist2tsv(inp, header=None):
    output = ''
    if header is not None:
        inp.insert(0, header)
    inp = flatten2d(inp)
    for row in inp:
        output = output + '\t'.join(str(item) for item in row) + '\n'
    return output

# Return the value indexed if it is a list, or simply the value otherwise.
def index_if_list(value, index):
    return value[index] if isinstance(value, list) else value

def html_line_breaks(inp):
    return inp.replace('\n', '<br />') if isinstance(inp, str) else inp

def graphviz_line_breaks(inp):
    return inp.replace('\n', '\\n') if isinstance(inp, str) else inp # \n generates centered new lines. http://www.graphviz.org/doc/info/attrs.html#k:escString

def remove_line_breaks(inp):
    return inp.replace('\n', ' ').rstrip() if isinstance(inp, str) else inp
