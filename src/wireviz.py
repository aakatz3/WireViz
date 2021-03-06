#!/usr/bin/env python3
import os
from dataclasses import dataclass, field
from typing import Any, List
from collections import Counter
import yaml
from graphviz import Graph

import wv_colors
from wv_helper import nested, int2tuple, awg_equiv, flatten2d, tuplelist2tsv

class Harness:

    def __init__(self):
        self.color_mode = 'SHORT'
        self.connectors = {}
        self.cables = {}

    def add_connector(self, name, *args, **kwargs):
        self.connectors[name] = Connector(name, *args, **kwargs)

    def add_cable(self, name, *args, **kwargs):
        self.cables[name] = Cable(name, *args, **kwargs)

    def loop(self, connector_name, from_pin, to_pin):
        self.connectors[connector_name].loop(from_pin, to_pin)

    def connect(self, from_name, from_pin, via_name, via_pin, to_name, to_pin):
        self.cables[via_name].connect(from_name, from_pin, via_pin, to_name, to_pin)
        if from_name in self.connectors:
            self.connectors[from_name].activate_pin(from_pin)
        if to_name in self.connectors:
            self.connectors[to_name].activate_pin(to_pin)

    def create_graph(self):
        dot = Graph()
        dot.body.append('// Graph generated by WireViz')
        dot.body.append('// https://github.com/formatc1702/WireViz')
        font = 'arial'
        dot.attr('graph', rankdir='LR',
                          ranksep='2',
                          bgcolor='white',
                          nodesep='0.33',
                          fontname=font)
        dot.attr('node', shape='record',
                         style='filled',
                         fillcolor='white',
                         fontname=font)
        dot.attr('edge', style='bold',
                         fontname=font)

        # prepare ports on connectors depending on which side they will connect
        for k, c in self.cables.items():
            for x in c.connections:
                if x.from_port is not None: # connect to left
                    self.connectors[x.from_name].ports_right = True
                if x.to_port is not None: # connect to right
                    self.connectors[x.to_name].ports_left = True

        for k, n in self.connectors.items():
            if n.category == 'ferrule':
                infostring = '{type}{subtype} {color}'.format(type=n.type,
                                                               subtype=', {}'.format(n.subtype) if n.subtype else '',
                                                               color=wv_colors.translate_color(n.color, self.color_mode) if n.color else '')
                infostring_l = infostring if n.ports_right else ''
                infostring_r = infostring if n.ports_left else ''

                dot.node(k, shape='none',
                            style='filled',
                            margin='0',
                            orientation = '0' if n.ports_left else '180',
                            label='''<

                <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="2"><TR>
                <TD PORT="p1l"> {infostring_l} </TD>
                {colorbar}
                <TD PORT="p1r"> {infostring_r} </TD>
                </TR></TABLE>


                >'''.format(infostring_l=infostring_l,
                            infostring_r=infostring_r,
                            colorbar='<TD BGCOLOR="{}" BORDER="1" SIDES="LR" WIDTH="4"></TD>'.format(wv_colors.translate_color(n.color, 'HEX')) if n.color else ''))

            else: # not a ferrule
                # a = attributes
                a = [n.part_number, n.type,
                     n.subtype,
                     '{}-pin'.format(len(n.pinout)) if n.show_pincount else '']
                # p = pinout
                p = [[],[],[]]
                for i, x in enumerate(n.pinout, 1):
                    if n.hide_disconnected_pins and not n.visible_pins.get(i, False):
                        continue
                    p[1].append(x)
                    if n.ports_left:
                        p[0].append('<p{portno}l>{portno}'.format(portno=i))
                    if n.ports_right:
                        p[2].append('<p{portno}r>{portno}'.format(portno=i))
                # l = label
                l = [n.name if n.show_name else '', a, p, n.notes]
                dot.node(k, label=nested(l))

                if len(n.loops) > 0:
                    dot.attr('edge',color='#000000:#ffffff:#000000')
                    if n.ports_left:
                        loop_side = 'l'
                        loop_dir = 'w'
                    elif n.ports_right:
                        loop_side = 'r'
                        loop_dir = 'e'
                    else:
                        raise Exception('No side for loops')
                    for loop in n.loops:
                        dot.edge('{name}:p{port_from}{loop_side}:{loop_dir}'.format(name=n.name, port_from=loop[0], port_to=loop[1], loop_side=loop_side, loop_dir=loop_dir),
                                 '{name}:p{port_to}{loop_side}:{loop_dir}'.format(name=n.name, port_from=loop[0], port_to=loop[1], loop_side=loop_side, loop_dir=loop_dir))

        for k, c in self.cables.items():
            # a = attributes
            a = [c.part_number,
                 '{}x'.format(len(c.colors)) if c.show_wirecount else '',
                 '{} {}{}'.format(c.gauge, c.gauge_unit, ' ({} AWG)'.format(awg_equiv(c.gauge)) if c.gauge_unit == 'mm\u00B2' and c.show_equiv else '') if c.gauge else '', # TODO: show equiv
                 '+ S' if c.shield else '',
                 '{} m'.format(c.length) if c.length > 0 else '']
            a = list(filter(None, a))

            html = '<table border="0" cellspacing="0" cellpadding="0"><tr><td>' # main table

            html = html + '<table border="0" cellspacing="0" cellpadding="3" cellborder="1">' # name+attributes table
            if c.show_name:
                html = html + '<tr><td colspan="{colspan}">{name}</td></tr>'.format(colspan=len(a), name=c.name)
            html = html + '<tr>' # attribute row
            for attrib in a:
                html = html + '<td>{attrib}</td>'.format(attrib=attrib)
            html = html + '</tr>' # attribute row
            html = html + '</table></td></tr>' # name+attributes table

            html = html + '<tr><td>&nbsp;</td></tr>' # spacer between attributes and wires

            html = html + '<tr><td><table border="0" cellspacing="0" cellborder="0">' # conductor table

            for i, x in enumerate(c.colors,1):
                p = []
                p.append('<!-- {}_in -->'.format(i))
                p.append(wv_colors.translate_color(x, self.color_mode))
                p.append('<!-- {}_out -->'.format(i))
                html = html + '<tr>'
                for bla in p:
                    html = html + '<td>{}</td>'.format(bla)
                html = html + '</tr>'
                bgcolor = wv_colors.translate_color(x, 'hex')
                html = html + '<tr><td colspan="{colspan}" cellpadding="0" height="6" bgcolor="{bgcolor}" border="2" sides="tb" port="{port}"></td></tr>'.format(colspan=len(p), bgcolor=bgcolor if bgcolor != '' else '#ffffff', port='w{}'.format(i))

            if c.shield:
                p = ['<!-- s_in -->', 'Shield', '<!-- s_out -->']
                html = html + '<tr><td>&nbsp;</td></tr>' # spacer
                html = html + '<tr>'
                for bla in p:
                    html = html + '<td>{}</td>'.format(bla)
                html = html + '</tr>'
                html = html + '<tr><td colspan="{colspan}" cellpadding="0" height="6" border="2" sides="b" port="{port}"></td></tr>'.format(colspan=len(p), bgcolor=wv_colors.translate_color(x, 'hex'), port='ws')

            html = html + '<tr><td>&nbsp;</td></tr>' # spacer at the end

            html = html + '</table>' # conductor table

            html = html + '</td></tr>'  # main table
            if c.notes:
                html = html + '<tr><td cellpadding="3">{}</td></tr>'.format(c.notes) # notes table
                html = html + '<tr><td>&nbsp;</td></tr>' # spacer at the end

            html = html + '</table>'  # main table

            # connections
            for x in c.connections:
                if isinstance(x.via_port, int): # check if it's an actual wire and not a shield
                    search_color = c.colors[x.via_port-1]
                    if search_color in wv_colors.color_hex:
                        dot.attr('edge',color='#000000:{wire_color}:#000000'.format(wire_color=wv_colors.color_hex[search_color]))
                    else: # color name not found
                        dot.attr('edge',color='#000000:#ffffff:#000000')
                else: # it's a shield connection
                    dot.attr('edge',color='#000000')

                if x.from_port is not None: # connect to left
                    from_ferrule = self.connectors[x.from_name].category == 'ferrule'
                    code_left_1 = '{from_name}{from_port}:e'.format(from_name=x.from_name, from_port=':p{}r'.format(x.from_port) if not from_ferrule else '')
                    code_left_2 = '{via_name}:w{via_wire}:w'.format(via_name=c.name, via_wire=x.via_port, via_subport='i' if c.show_pinout else '')
                    dot.edge(code_left_1, code_left_2)
                    from_string = '{}:{}'.format(x.from_name, x.from_port) if not from_ferrule else ''
                    html = html.replace('<!-- {}_in -->'.format(x.via_port), from_string)
                if x.to_port is not None: # connect to right
                    to_ferrule = self.connectors[x.to_name].category == 'ferrule'
                    code_right_1 = '{via_name}:w{via_wire}:e'.format(via_name=c.name, via_wire=x.via_port, via_subport='o' if c.show_pinout else '')
                    code_right_2 = '{to_name}{to_port}:w'.format(to_name=x.to_name, to_port=':p{}l'.format(x.to_port) if not to_ferrule else '')
                    dot.edge(code_right_1, code_right_2)
                    to_string = '{}:{}'.format(x.to_name, x.to_port) if not to_ferrule else ''
                    html = html.replace('<!-- {}_out -->'.format(x.via_port), to_string)

            dot.node(c.name, label='<{html}>'.format(html=html), shape='box', style='filled,dashed' if c.category=='bundle' else '', margin='0', fillcolor='white')

        return dot

    def output(self, filename, directory='_output', view=False, cleanup=True, format='pdf', gen_bom=False):
        # graphical output
        d = self.create_graph()
        for f in format:
            d.format = f
            d.render(filename=filename, directory=directory, view=view, cleanup=cleanup)
        d.save(filename='{}.gv'.format(filename), directory=directory)
        # bom output
        bom_list = self.bom_list()
        with open('{}.bom.tsv'.format(filename),'w') as file:
            file.write(tuplelist2tsv(bom_list))
        # HTML output
        with open('{}.html'.format(filename),'w') as file:
            file.write('<html><body style="font-family:Arial">')

            file.write('<h1>Diagram</h1>')
            with open('{}.svg'.format(filename),'r') as svg:
                for l in svg:
                    file.write(l)

            file.write('<h1>Bill of Materials</h1>')
            listy = flatten2d(bom_list)
            file.write('<table style="border:1px solid #000000; font-size: 14pt; border-spacing: 0px">')
            file.write('<tr>')
            for item in listy[0]:
                file.write('<th align="left" style="border:1px solid #000000; padding: 8px">{}</th>'.format(item))
            file.write('</tr>')
            for row in listy[1:]:
                file.write('<tr>')
                for i, item in enumerate(row):
                    file.write('<td {align} style="border:1px solid #000000; padding: 4px">{content}</td>'.format(content=item, align='align="right"' if listy[0][i] == 'Qty' else ''))
                file.write('</tr>')
            file.write('</table>')

            file.write('</body></html>')

    def bom(self):
        bom = []
        bom_connectors = []
        bom_cables = []
        # connectors
        types = Counter([(v.type, v.subtype, v.pincount) for v in self.connectors.values()])
        for type in types:
            items = {k: v for k, v in self.connectors.items()  if (v.type, v.subtype, v.pincount) == type}
            shared = next(iter(items.values()))
            designators = list(items.keys())
            designators.sort()
            part_number = shared.part_number
            name = 'Connector{type}{subtype}{pincount}{color}'.format(type = ', {}'.format(shared.type) if shared.type else '',
                                                      subtype = ', {}'.format(shared.subtype) if shared.subtype else '',
                                                      pincount = ', {} pins'.format(shared.pincount) if shared.category != 'ferrule' else '',
                                                      color = ', {}'.format(shared.color) if shared.color else '')
            item = {'item': name, 'qty': len(designators), 'unit': '', 'designators': designators if shared.category != 'ferrule' else ''}
            if part_number is not None:  # set part number only if it exists
                item['part number'] = part_number
            bom_connectors.append(item)
            bom_connectors = sorted(bom_connectors, key=lambda k: k['item']) # https://stackoverflow.com/a/73050
        bom.extend(bom_connectors)
        # cables
        types = Counter([(v.category, v.gauge, v.gauge_unit, v.wirecount, v.shield) for v in self.cables.values()])
        for type in types:
            items = {k: v for k, v in self.cables.items() if (v.category, v.gauge, v.gauge_unit, v.wirecount, v.shield) == type}
            shared = next(iter(items.values()))
            if shared.category != 'bundle':
                designators = list(items.keys())
                designators.sort()
                part_number = shared.part_number
                total_length = sum(i.length for i in items.values())
                name = 'Cable, {wirecount}{gauge}{shield}'.format(wirecount = shared.wirecount,
                                                                   gauge = ' x {} {}'.format(shared.gauge, shared.gauge_unit) if shared.gauge else ' wires',
                                                                   shield = ' shielded' if shared.shield else '')
                item = {'item': name, 'qty': round(total_length, 3), 'unit': 'm', 'designators': designators}
                if part_number is not None:  # set part number only if it exists
                    item['part number'] = part_number
                bom_cables.append(item)
        # bundles (ignores wirecount)
        wirelist = []
        # list all cables again, since bundles are represented as wires internally, with the category='bundle' set
        types = Counter([(v.category, v.gauge, v.gauge_unit, v.length) for v in self.cables.values()])
        for type in types:
            items = {k: v for k, v in self.cables.items() if (v.category, v.gauge, v.gauge_unit, v.length) == type}
            shared = next(iter(items.values()))
            # filter out cables that are not bundles
            if shared.category == 'bundle':
                for bundle in items.values():
                    # add each wire from each bundle to the wirelist
                    for color in bundle.colors:
                        wirelist.append({'gauge': shared.gauge, 'gauge_unit': shared.gauge_unit, 'length': shared.length, 'color': color, 'designators': list(items.keys())})
        # join similar wires from all the bundles to a single BOM item
        types = Counter([(v['gauge'], v['gauge_unit'], v['color']) for v in wirelist])
        for type in types:
            items = [v for v in wirelist if (v['gauge'], v['gauge_unit'], v['color']) == type]
            shared = items[0]
            designators = [i['designators'] for i in items]
            # flatten nested list
            designators = [item for sublist in designators for item in sublist] # https://stackoverflow.com/a/952952
            # remove duplicates
            designators = list(dict.fromkeys(designators))
            designators.sort()
            total_length = sum(i['length'] for i in items)
            name = 'Wire, {gauge}{color}'.format(gauge='{} {}'.format(shared['gauge'], shared['gauge_unit']) if shared['gauge'] else '',
                                                 color=', {}'.format(shared['color']) if shared['color'] != '' else '')
            item = {'item': name, 'qty': round(total_length, 3), 'unit': 'm', 'designators': designators}
            bom_cables.append(item)
            bom_cables = sorted(bom_cables, key=lambda k: k['item']) # https://stackoverflow.com/a/73050
        bom.extend(bom_cables)
        return bom

    def bom_list(self):
        bom = self.bom()
        keys = ['item', 'qty', 'unit', 'designators']
        # check if any part numbers are set
        if any("part number" in x for x in bom):
            keys.append("part number")
        bom_list = []
        bom_list.append([k.capitalize() for k in keys]) # create header row with keys
        for item in bom:
            item_list = [item.get(key, '') for key in keys] # fill missing values with blanks
            for i, subitem in enumerate(item_list):
                if isinstance(subitem, List): # convert any lists into comma separated strings
                    item_list[i] = ', '.join(subitem)
            bom_list.append(item_list)
        return bom_list

@dataclass
class Connector:
    name: str
    part_number: str = None
    category: str = None
    type: str = None
    subtype: str = None
    pincount: int = None
    notes: str = None
    pinout: List[Any] = field(default_factory=list)
    color: str = None
    show_name: bool = True
    show_pincount: bool = True
    hide_disconnected_pins: bool = False

    def __post_init__(self):
        self.ports_left = False
        self.ports_right = False
        self.loops = []
        self.visible_pins = {}

        if self.pinout:
            if self.pincount is not None:
                raise Exception('You cannot specify both pinout and pincount')
            else:
                self.pincount = len(self.pinout)
        else:
            if not self.pincount:
                self.pincount = 1
            self.pinout = ['',] * self.pincount

    def loop(self, from_pin, to_pin):
        self.loops.append((from_pin, to_pin))
        if self.hide_disconnected_pins:
            self.visible_pins[from_pin] = True
            self.visible_pins[to_pin] = True

    def activate_pin(self, pin):
        self.visible_pins[pin] = True

@dataclass
class Cable:
    name: str
    part_number: str = None
    category : str = None
    type: str = None
    gauge: float = None
    gauge_unit : str = None
    show_equiv: bool = False
    length: float = 0
    wirecount: int = None
    shield: bool = False
    notes: str = None
    colors: List[Any] = field(default_factory=list)
    color_code: str = None
    show_name: bool = True
    show_pinout: bool = False
    show_wirecount: bool = True

    def __post_init__(self):

        if isinstance(self.gauge, str): # gauge and unit specified
            try:
                g, u = self.gauge.split(' ')
            except:
                raise Exception('Gauge must be a number, or number and unit separated by a space')
            self.gauge = g
            self.gauge_unit = u.replace('mm2','mm\u00B2')
        elif self.gauge is not None: # gauge specified, assume mm2
            if self.gauge_unit is None:
                self.gauge_unit = 'mm\u00B2'
        else:
            pass # gauge not specified

        self.connections = []

        if self.wirecount: # number of wires explicitly defined
            if self.colors: # use custom color palette (partly or looped if needed)
                pass
            elif self.color_code: # use standard color palette (partly or looped if needed)
                if self.color_code not in wv_colors.COLOR_CODES:
                    raise Exception('Unknown color code')
                self.colors = wv_colors.COLOR_CODES[self.color_code]
            else: # no colors defined, add dummy colors
                self.colors = [''] * self.wirecount

            # make color code loop around if more wires than colors
            if self.wirecount > len(self.colors):
                 m = self.wirecount // len(self.colors) + 1
                 self.colors = self.colors * int(m)
            # cut off excess after looping
            self.colors = self.colors[:self.wirecount]
        else: # wirecount implicit in length of color list
            if not self.colors:
                raise Exception('Unknown number of wires. Must specify wirecount or colors (implicit length)')
            self.wirecount = len(self.colors)

        # for BOM generation
        self.wirecount_and_shield = (self.wirecount, self.shield)

    def connect(self, from_name, from_pin, via_pin, to_name, to_pin):
        from_pin = int2tuple(from_pin)
        via_pin  = int2tuple(via_pin)
        to_pin   = int2tuple(to_pin)
        if len(from_pin) != len(to_pin):
            raise Exception('from_pin must have the same number of elements as to_pin')
        for i, x in enumerate(from_pin):
            # self.connections.append((from_name, from_pin[i], via_pin[i], to_name, to_pin[i]))
            self.connections.append(Connection(from_name, from_pin[i], via_pin[i], to_name, to_pin[i]))

@dataclass
class Connection:
    from_name: Any
    from_port: Any
    via_port:  Any
    to_name:   Any
    to_port:   Any

def parse(file_in, file_out=None, gen_bom=False):

    file_in = os.path.abspath(file_in)
    if not file_out:
        file_out = file_in
        pre, ext = os.path.splitext(file_out)
        file_out = pre # extension will be added by graphviz output function
    file_out = os.path.abspath(file_out)

    with open(file_in, 'r') as stream:
        input = yaml.safe_load(stream)

    def expand(input):
        # input can be:
        # - a singleton (normally str or int)
        # - a list of str or int
        # if str is of the format '#-#', it is treated as a range (inclusive) and expanded
        output = []
        if not isinstance(input, list):
            input = [input,]
        for e in input:
            e = str(e)
            if '-' in e: # list of pins
                a, b = tuple(map(int, e.split('-')))
                if a < b:
                    for x in range(a,b+1):
                        output.append(x)
                elif a > b:
                    for x in range(a,b-1,-1):
                        output.append(x)
                elif a == b:
                    output.append(a)
            else:
                try:
                    x = int(e)
                except:
                    x = e
                output.append(x)
        return output

    def check_designators(what, where):
        for i, x in enumerate(what):
            if x not in input[where[i]]:
                return False
        return True

    h = Harness()

    # add items
    sections = ['connectors','cables','ferrules','connections']
    types    = [dict, dict, dict, list]
    for sec, ty in zip(sections, types):
        if sec in input and type(input[sec]) == ty:
            if len(input[sec]) > 0:
                if ty == dict:
                    for k, o in input[sec].items():
                        if sec == 'connectors':
                            h.add_connector(name=k, **o)
                        elif sec == 'cables':
                            h.add_cable(name=k, **o)
                        elif sec == 'ferrules':
                            pass
            else:
                pass # section exists but is empty
        else: # section does not exist, create empty section
            if ty == dict:
                input[sec] = {}
            elif ty == list:
                input[sec] = []

    # add connections
    ferrule_counter = 0
    for con in input['connections']:
        if len(con) == 3: # format: connector -- cable -- conector

            for c in con:
                if len(list(c.keys())) != 1: # check that each entry in con has only one key, which is the designator
                    raise Exception('Too many keys')

            from_name = list(con[0].keys())[0]
            via_name  = list(con[1].keys())[0]
            to_name   = list(con[2].keys())[0]

            if not check_designators([from_name,via_name,to_name],('connectors','cables','connectors')):
                print([from_name,via_name,to_name])
                raise Exception('Bad connection definition (3)')

            from_pins = expand(con[0][from_name])
            via_pins  = expand(con[1][via_name])
            to_pins   = expand(con[2][to_name])

            if len(from_pins) != len(via_pins) or len(via_pins) != len(to_pins):
                raise Exception('List length mismatch')

            for (from_pin, via_pin, to_pin) in zip(from_pins, via_pins, to_pins):
                h.connect(from_name, from_pin, via_name, via_pin, to_name, to_pin)

        elif len(con) == 2:

            for c in con:
                if type(c) is dict:
                    if len(list(c.keys())) != 1: # check that each entry in con has only one key, which is the designator
                        raise Exception('Too many keys')

            # hack to make the format for ferrules compatible with the formats for connectors and cables
            if type(con[0]) == str:
                name = con[0]
                con[0] = {}
                con[0][name] = name
            if type(con[1]) == str:
                name = con[1]
                con[1] = {}
                con[1][name] = name

            from_name = list(con[0].keys())[0]
            to_name   = list(con[1].keys())[0]

            con_cbl = check_designators([from_name, to_name],('connectors','cables'))
            cbl_con = check_designators([from_name, to_name],('cables','connectors'))
            con_con = check_designators([from_name, to_name],('connectors','connectors'))


            fer_cbl = check_designators([from_name, to_name],('ferrules','cables'))
            cbl_fer = check_designators([from_name, to_name],('cables','ferrules'))

            if not con_cbl and not cbl_con and not con_con and not fer_cbl and not cbl_fer:
                raise Exception('Wrong designators')

            from_pins = expand(con[0][from_name])
            to_pins  = expand(con[1][to_name])

            if con_cbl or cbl_con or con_con:
                if len(from_pins) != len(to_pins):
                    raise Exception('List length mismatch')

            if con_cbl or cbl_con:
                for (from_pin, to_pin) in zip(from_pins, to_pins):
                    if con_cbl:
                        h.connect(from_name, from_pin, to_name, to_pin, None, None)
                    else: # cbl_con
                        h.connect(None, None, from_name, from_pin, to_name, to_pin)
            elif con_con:
                cocon_coname  = list(con[0].keys())[0]
                from_pins = expand(con[0][from_name])
                to_pins   = expand(con[1][to_name])

                for (from_pin, to_pin) in zip(from_pins, to_pins):
                    h.loop(cocon_coname, from_pin, to_pin)
            if fer_cbl or cbl_fer:
                from_pins = expand(con[0][from_name])
                to_pins   = expand(con[1][to_name])

                if fer_cbl:
                    ferrule_name = from_name
                    cable_name = to_name
                    cable_pins = to_pins
                else:
                    ferrule_name = to_name
                    cable_name = from_name
                    cable_pins = from_pins

                ferrule_params = input['ferrules'][ferrule_name]
                for cable_pin in cable_pins:
                    ferrule_counter = ferrule_counter + 1
                    ferrule_id = '_F{}'.format(ferrule_counter)
                    h.add_connector(ferrule_id, category='ferrule', **ferrule_params)

                    if fer_cbl:
                        h.connect(ferrule_id, 1, cable_name, cable_pin, None, None)
                    else:
                        h.connect(None, None, cable_name, cable_pin, ferrule_id, 1)


        else:
            raise Exception('Wrong number of connection parameters')

    h.output(filename=file_out, format=('png','svg'), gen_bom=gen_bom, view=False)

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('file_input', nargs='?', default='_test/test.yml')
    ap.add_argument('file_output', nargs='?', default=None)
    ap.add_argument('--bom', action='store_const', default=True, const=True)
    args = ap.parse_args()

    parse(args.file_input, file_out=args.file_output, gen_bom=args.bom)
