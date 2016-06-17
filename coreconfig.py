#!/usr/bin/env python

from libs.get_ipplan import Ipplan
from libs.devices import *
import settings
import yaml
import sqlite3
import os
import sys
import struct
import socket

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def get_asr_networks(c, terminator):
    """ Get networks that terminates in asr return as list of tuples"""

    networks = c.execute(
        'SELECT network.node_id, network.name, network.vlan, network.ipv4_txt, '
        'network.ipv6_txt, network.ipv4_netmask_txt, network.ipv6_netmask_txt '
        'FROM network '
        'WHERE terminator="D-ASR-V" '
        'AND network.name LIKE "EVENT@%" ')
    network_data = networks.fetchall()
    network_and_options = []
    for network in network_data:
        options = c.execute(
            'SELECT option.name, option.value '
            'FROM option '
            'WHERE option.node_id = ?', (network['node_id'],))
        option_data = options.fetchall()
        opt_dict = {}
        for option in option_data:
            opt_dict[option['name']] = option['value']
            network['options'] = opt_dict
        network_and_options.append(network)
    return sorted(network_and_options)

    #    'AND option.name = "vrf" '
    #    'AND option.node_id = network.node_id;', (terminator,))

def load_patchscheme(patchscheme_file):
    """ """
    with open(patchscheme_file, 'r') as stream:
        return yaml.load(stream)

class CoreConfig(object):
    """ """
    def __init__(self, patchscheme, networks, templates, configs):
        self.patchscheme = patchscheme
        self.networks = networks
        self.templates = templates
        self.configs = configs
        self.bundle_ids = []
        # Define config files
        self.bundles_file = settings.bundles_file
        
        # Populate switch objects
        self._populate_switches()

    def string_to_list(self, x):
        result = []
        for part in x.split(','):
            if '-' in part:
                a, b = part.split('-')
                a, b = int(a), int(b)
                result.extend(range(a, b + 1))
            else:
                a = int(part)
                result.append(a)
        return result

    def _populate_switches(self):
        self.switches = {}
        for k, v in self.patchscheme.iteritems():
            s = Switches(v['name'])
            s.set_hall(v['hall'])
            rows = self.string_to_list(v['rows'])
            s.set_rows([ str(x) + s.hall for x in rows ])
            s.set_bundle(self._bundle_id('Bundle-ether' + k))
            self.switches[s.name] = s

    def _asr_interface(self, interface):
        interface_two = interface.replace('0', '1', 1)
        return interface, interface_two

    def _interface_descr(self, interface):
        return self.patchscheme[interface]['name']

    def _bundle_id(self, interface):
        bundle_id = int(interface.split('/')[-1]) + 100
        return str(bundle_id)

    def create_bundles(self):
        """ Create bundle intefaces 
        
        We create the bundle configuration, the $INTERFACE1 and $INTERFACE2
        string replaceing is based on that the template matches the hard coded
        value
        """
        with open(self.templates['bundles'], 'r') as f:
            template_data = f.read()
        with open(self.configs['bundles'], 'w+') as f:
            for interface in self.patchscheme.iterkeys():
                interface_one, interface_two = self._asr_interface(interface)
                int_data = template_data.replace('$INTERFACE1$',
                                                 interface_one)
                int_data = int_data.replace('$INTERFACE2$',
                                            interface_two)
                interface_descr = self._interface_descr(interface_one)
                int_data = int_data.replace('$DESCRIPTION$',
                                             interface_descr)
                bundle_id = self._bundle_id(interface_one)
                int_data = int_data.replace('$BUNDLENUM$',
                                             bundle_id)
                f.write(int_data)

    def _ip2int(self, addr):
        return struct.unpack('!I', socket.inet_aton(addr))[0]

    def _int2ip(self, addr):
        return socket.inet_ntoa(struct.pack('!I', addr))

    def _gateway(self, addr):
        addr = str(addr).split('/')[0]
        return self._int2ip(self._ip2int(addr) + 1)

    def network_file(self, network):
        """ Which file to write the config to

        We want to have every table row in its own config file since 6k config
        lines in one file is a bit to much. Network -> DIST
        """

        for k, v in self.patchscheme.iteritems():
            bundle = 'Bundle-ether' + self._bundle_id(k)
            try:
                if bundle in network['options']['int']:
                    return v['name'] + ".r1"
                else:
                    continue
            except KeyError:
                continue

    def create_routers(self):
        """ Create router config

        Create router config using string replace
        """
        with open(self.templates['router']) as f:
            template_data = f.read()

        configs = {}
        for network in self.networks:
            if 'int' in network['options'].keys():
                if 'othernet' in network['options'].keys():
                    config_file = 'othernet.r1'
                bundle = network['options']['int']
                config_file = self.network_file(network)
                if config_file not in configs.keys():
                    configs[config_file] = ''
            else:
                print "NO INT option IN ", network
                continue

            vlanid = str(network['vlan'])
            name = network['name'].strip('EVENT@')
            ipvfour = network['ipv4_txt']
            ipvfour = self._gateway(ipvfour)
            ipvfour_netmask = str(network['ipv4_netmask_txt'])
            if 'vrf' in network['options'].keys():
                vrf = 'vrf ' + network['options']['vrf']
            else:
                vrf = "! VRF GLOBAL"

            # We dont use these atm
            ipvsix = network['ipv6_txt']
            ipvsix_netmask = network['ipv6_netmask_txt']

            bundle_data = template_data.replace('$int$', bundle)
            bundle_data = bundle_data.replace('$VLANID$', vlanid)
            bundle_data = bundle_data.replace('$IPV4-ADDR1$', ipvfour)
            bundle_data = bundle_data.replace('$IPV4-MASK$', ipvfour_netmask)
            bundle_data = bundle_data.replace('$vrf$', vrf)
            bundle_data = bundle_data.replace('$NAME$', name)

            configs[config_file] = configs[config_file] + bundle_data
            # Need to figure out in which file to put the config in,
            # it also has to be appended
        for k, v in configs.iteritems():
            if k:
                with open(settings.configs['routers'] + k, 'w+') as f:
                    f.write(v)
        
        def create_switches(self):
            """ Create Switch configs

            Generate switch configuration, vlanid port and row
            """



def main():
    """ Coreconfig """

    if not settings.ipplan_file in os.listdir('./'):
        p = Ipplan(settings.url,
                   settings.ipplan_user,
                   settings.ipplan_password)
        p.to_file()
        db = p.get_ipplan()
    else:
        db = settings.ipplan_file

    conn = sqlite3.connect(db)
    conn.row_factory = dict_factory
    c = conn.cursor()

    # Get all network info from ipplan
    networks = get_asr_networks(c, settings.terminator)

    # Load the patchscheme
    patchscheme = load_patchscheme(settings.patchscheme)

    # Load templates, core and dist
    core = CoreConfig(patchscheme,
                      networks,
                      settings.templates,
                      settings.configs)
    core.create_bundles()
    core.create_routers()

if __name__ == "__main__":
    main()
