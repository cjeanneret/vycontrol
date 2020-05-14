from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader
from django.shortcuts import redirect
from django.conf import settings
from django.urls import reverse

import vyos, vyos2
from performance import timer
from perms import is_authenticated
import perms
import network
import json
import pprint

from filters.vycontrol_filters import get_item
from filters.vycontrol_filters import get_item_port
from filters.vycontrol_filters import get_item_network

@is_authenticated
def index(request):
    #interfaces = vyos.get_interfaces()
    all_instances = vyos.instance_getall_by_group(request)
    hostname_default = vyos.get_hostname_prefered(request)


    firewall2 = vyos2.api(
        hostname =      hostname_default,
        api =           'get',
        op =            'showConfig',
        cmd =           {"op": "showConfig", "path": ["firewall"]},
        description =   "get all firewall",
    )



    is_superuser = perms.get_is_superuser(request.user)



    firewall_all = vyos.get_firewall_all(hostname_default)
    if firewall_all == False:
        return redirect('firewall:firewall-create')

    for xitem in firewall_all['name']:
        if 'default-action' in firewall_all['name'][xitem]:
            firewall_all['name'][xitem]['default_action'] = firewall_all['name'][xitem]['default-action']
            del firewall_all['name'][xitem]['default-action']

    template = loader.get_template('firewall/list.html')
    context = { 
        #'interfaces': interfaces,
        'instances': all_instances,
        'hostname_default': hostname_default,
        'firewall_all':  firewall_all,
        'username': request.user,
        'is_superuser' : is_superuser,
    }   
    return HttpResponse(template.render(context, request))

@is_authenticated
def create(request):
        
    #interfaces = vyos.get_interfaces()
    all_instances = vyos.instance_getall()
    hostname_default = vyos.get_hostname_prefered(request)
    is_superuser = perms.get_is_superuser(request.user)

    if 'name' in request.POST:
        cmd = {"op": "set", "path": ["firewall", "name", request.POST['name']]}
        result1 = vyos.set_config(hostname_default, cmd)
        print(result1)

        if 'description' in request.POST:
            cmd = {"op": "set", "path": ["firewall", "name", request.POST['name'], "description", request.POST['description']]}
            result2 = vyos.set_config(hostname_default, cmd)
            print(result2)

        if 'action' in request.POST:
            cmd = {"op": "set", "path": ["firewall", "name", request.POST['name'], "default-action", request.POST['action']]}
            result3 = vyos.set_config(hostname_default, cmd)
            print(result3)

        return redirect('firewall:firewall-list')

    template = loader.get_template('firewall/create.html')
    context = { 
        #'interfaces': interfaces,
        'instances': all_instances,
        'hostname_default': hostname_default,
        'username': request.user,
        'is_superuser' : is_superuser,
    }   
    return HttpResponse(template.render(context, request))

@is_authenticated
def addrule(request, firewall_name):
        
    #interfaces = vyos.get_interfaces()
    all_instances = vyos.instance_getall()
    hostname_default = vyos.get_hostname_prefered(request)
    is_superuser = perms.get_is_superuser(request.user)
    firewall = vyos.get_firewall(hostname_default, firewall_name)
    firewall_networkgroup = vyos.get_firewall_networkgroup(hostname_default)
    firewall_addressgroup = vyos.get_firewall_addressgroup(hostname_default)
    firewall_networkgroup_js = json.dumps(firewall_networkgroup['network-group'])
    firewall_addressgroup_js = json.dumps(firewall_addressgroup['address-group'])
    netservices = network.get_services()
    netservices_js = json.dumps(netservices)
    portgroups = vyos.get_firewall_portgroup(hostname_default)

    if portgroups != False:
        portgroups_groups = portgroups['port-group']
    else:
        portgroups_groups = []

    changed = False


    # verifing basic informations, should have rulenumber, status and ruleaction
    if (    request.POST.get('rulenumber', None) != None 
        and int(request.POST.get('rulenumber')) > 0
        and request.POST.get('status', None) != None
        and request.POST.get('status') in ["enabled", "disabled"]
        and request.POST.get('ruleaction', None) != None
        and request.POST.get('ruleaction') in ["accept", "drop", "reject"]
    ):
        vyos2.log("basic pass x")


        v = vyos2.api (
            hostname=   hostname_default,
            api =       "post",
            op =        "set",
            cmd =       ["firewall", "name", firewall_name, "rule", request.POST.get('rulenumber'), "action", request.POST.get('ruleaction')],
            description = "set rule action",
        )
        # rule created, continue to configure firewall rule according his criterias
        if v.success:
            changed = True 

            # if status disabled, save it
            if request.POST.get('status') == "disabled":
                v = vyos2.api (
                    hostname=   hostname_default,
                    api =       "post",
                    op =        "set",
                    cmd =       ["firewall", "name", firewall_name, "rule", request.POST.get('rulenumber'), "disable"],
                    description = "set rule disable",
                )

            # if status set, save it
            if request.POST.get('description', None) != None:
                v = vyos2.api (
                    hostname=   hostname_default,
                    api =       "post",
                    op =        "set",
                    cmd =       ["firewall", "name", firewall_name, "rule", request.POST.get('rulenumber'), "description", request.POST.get('description')],
                    description = "set rule description",
                )     

            # if criteria protocol set, save it
            if request.POST.get('criteria_protocol', None) == "1":
                # other protocol - todo validate data
                if request.POST.get('protocol_criteria', None) == "other":
                    if request.POST.get('protocol_custom', None) != None:
                        protocol_criteria = request.POST.get('protocol_custom')
                # common protocols
                elif request.POST.get('protocol_criteria', None) in ['all', 'tcp', 'udp', 'tcp_udp', 'icmp']:
                    protocol_criteria = request.POST.get('protocol_criteria')
                # other cases did not checked anything
                else:
                     protocol_criteria = None   

                # negate protocol
                if request.POST.get('protocol_negate', None) == "1":
                    protocol_negate = "!"
                else:
                    protocol_negate = ""

                # run vyos command
                if protocol_criteria != None:
                    protocol_criteria_txt = protocol_negate + protocol_criteria

                    v = vyos2.api (
                        hostname=   hostname_default,
                        api =       "post",
                        op =        "set",
                        cmd =       ["firewall", "name", firewall_name, "rule", request.POST.get('rulenumber'), "protocol", protocol_criteria_txt],
                        description = "set rule protocol",
                    )                                

            # if criteria port set, save it
            if request.POST.get('criteria_port', None) == "1":
                destinationport_json =  request.POST.get('destinationport_json', None)
                sourceport_json =       request.POST.get('sourceport_json', None)

                if destinationport_json != None:

                    try:
                        destinationport = json.loads(destinationport_json)
                    except ValueError:
                        destinationport = {}

                    vyos2.log("destinationport_json", destinationport)
                    destinationport_text = ','.join(destinationport)

                    
                    v = vyos2.api (
                        hostname=   hostname_default,
                        api =       "post",
                        op =        "set",
                        cmd =       ["firewall", "name", firewall_name, "rule", request.POST.get('rulenumber'), "destination", "port", destinationport_text],
                        description = "set destination port",
                    ) 

                if sourceport_json != None:

                    try:
                        sourceport = json.loads(sourceport_json)
                    except ValueError:
                        sourceport = {}          

                    vyos2.log("sourceport_json", sourceport)
                    sourceport_text = ','.join(sourceport)

                    v = vyos2.api (
                        hostname=   hostname_default,
                        api =       "post",
                        op =        "set",
                        cmd =       ["firewall", "name", firewall_name, "rule", request.POST.get('rulenumber'), "source", "port", sourceport_text],
                        description = "set sourceport port",
                    )

            # if criteria port set, save it
            if request.POST.get('criteria_address', None) == "1":
                # negate sdaddress_source
                if request.POST.get('sdaddress_source_negate', None) == "1":
                    sdaddress_source_negate = "!"
                else:
                    sdaddress_source_negate = ""

                # negate sdaddress_destination_negate
                if request.POST.get('sdaddress_destination_negate', None) == "1":
                    sdaddress_destination_negate = "!"
                else:
                    sdaddress_destination_negate = ""                    


                if request.POST.get('sdaddress_source', None) != None:              
                    sdaddress_source = request.POST.get('sdaddress_source')
                    sdaddress_source_txt = sdaddress_source_negate + sdaddress_source
                    
                    v = vyos2.api (
                        hostname=   hostname_default,
                        api =       "post",
                        op =        "set",
                        cmd =       ["firewall", "name", firewall_name, "rule", request.POST.get('rulenumber'), "source", "address", sdaddress_source_txt],
                        description = "set sdaddress_source",
                    )


                if request.POST.get('sdaddress_destination', None) != None:              
                    sdaddress_destination = request.POST.get('sdaddress_destination')                    
                    sdaddress_destination_txt = sdaddress_destination_negate + sdaddress_destination

                    v = vyos2.api (
                        hostname=   hostname_default,
                        api =       "post",
                        op =        "set",
                        cmd =       ["firewall", "name", firewall_name, "rule", request.POST.get('rulenumber'), "destination", "address", sdaddress_destination_txt],
                        description = "set sdaddress_destination_txt",
                    )






    """
  



        #""if 'protocol' in request.POST:
            cmd = {"op": "set", "path": ["firewall", "name", firewall_name, "rule", request.POST['rulenumber'], "protocol", request.POST['protocol']]}
            result2 = vyos.set_config(hostname_default, cmd)
            print(result2)
            changed = True

        if 'destinationport' in request.POST:
            cmd = {"op": "set", "path": ["firewall", "name", firewall_name, "rule", request.POST['rulenumber'], "destination", "port", request.POST['destinationport']]}
            result3 = vyos.set_config(hostname_default, cmd)
            print(result3)
            changed = True

        if 'sourceport' in request.POST:
            cmd = {"op": "set", "path": ["firewall", "name", firewall_name, "rule", request.POST['rulenumber'], "source", "port", request.POST['sourceport']]}
            result3 = vyos.set_config(hostname_default, cmd)
            print(result3)        
            changed = True""#

        if changed == True:
            return redirect('firewall:show', firewall_name)"""
    

    template = loader.get_template('firewall/addrule.html')
    context = { 
        #'interfaces': interfaces,
        'instances': all_instances,
        'hostname_default': hostname_default,
        'firewall':  firewall,
        'firewall_name': firewall_name,
        'username': request.user,
        'is_superuser' : is_superuser,
        'services' : netservices['services'],
        'services_common' : netservices['common'],
        'firewall_networkgroup': firewall_networkgroup['network-group'],
        'firewall_addressgroup': firewall_addressgroup['address-group'],
        'firewall_networkgroup_js': firewall_networkgroup_js,
        'firewall_addressgroup_js': firewall_addressgroup_js,
        'netservices_js' : netservices_js,
        'portgroups_groups': portgroups_groups,
    }  
    return HttpResponse(template.render(context, request))

@is_authenticated
def firewall_removerule(request, firewall_name, firewall_rulenumber):
    all_instances = vyos.instance_getall()
    hostname_default = vyos.get_hostname_prefered(request)

    firewall = vyos.get_firewall(hostname_default, firewall_name)
    firewall_rule = vyos.get_firewall_rule(hostname_default, firewall_name, firewall_rulenumber)

    if firewall_rule and firewall:
        vyos.delete_route_rule(hostname_default, firewall_name, firewall_rulenumber)

    return redirect('firewall:show', firewall_name)

@is_authenticated
def editrule(request, firewall_name, firewall_rulenumber):
    #interfaces = vyos.get_interfaces()
    all_instances = vyos.instance_getall()
    hostname_default = vyos.get_hostname_prefered(request)
    is_superuser = perms.get_is_superuser(request.user)

    firewall = vyos.get_firewall(hostname_default, firewall_name)
    firewall_rule = vyos.get_firewall_rule(hostname_default, firewall_name, firewall_rulenumber)

    changed = False

    if 'action' in request.POST:
        cmd = {"op": "set", "path": ["firewall", "name", firewall_name, "rule", firewall_rulenumber, "action", request.POST['action']]}
        result1 = vyos.set_config(hostname_default, cmd)
        print(result1)
        changed = True

    if 'protocol' in request.POST:
        cmd = {"op": "set", "path": ["firewall", "name", firewall_name, "rule", firewall_rulenumber, "protocol", request.POST['protocol']]}
        result2 = vyos.set_config(hostname_default, cmd)
        print(result2)
        changed = True

    if 'destinationport' in request.POST:
        cmd = {"op": "set", "path": ["firewall", "name", firewall_name, "rule", firewall_rulenumber, "destination", "port", request.POST['destinationport']]}
        result3 = vyos.set_config(hostname_default, cmd)
        print(result3)
        changed = True

    if 'sourceport' in request.POST:
        cmd = {"op": "set", "path": ["firewall", "name", firewall_name, "rule", firewall_rulenumber, "source", "port", request.POST['sourceport']]}
        result3 = vyos.set_config(hostname_default, cmd)
        print(result3)
        changed = True        

    if changed == True:
        return redirect('firewall:firewall-list')


    template = loader.get_template('firewall/editrule.html')
    context = { 
        #'interfaces': interfaces,
        'instances': all_instances,
        'hostname_default': hostname_default,
        'firewall':  firewall,
        'firewall_name': firewall_name,
        'firewall_rule': firewall_rule,
        'firewall_rulenumber' : firewall_rulenumber,
        'username': request.user,
        'is_superuser' : is_superuser,
    }  
    return HttpResponse(template.render(context, request))

@is_authenticated
def show(request, firewall_name):
        
    #interfaces = vyos.get_interfaces()
    all_instances = vyos.instance_getall()
    hostname_default = vyos.get_hostname_prefered(request)
    is_superuser = perms.get_is_superuser(request.user)

    firewall = vyos.get_firewall(hostname_default, firewall_name)
    

    template = loader.get_template('firewall/show.html')
    context = { 
        #'interfaces': interfaces,
        'instances': all_instances,
        'hostname_default': hostname_default,
        'firewall':  firewall,
        'firewall_name': firewall_name,
        'username': request.user,
        'is_superuser' : is_superuser,
    }   
    return HttpResponse(template.render(context, request))

@is_authenticated
def firewall_portgroup_list(request):
        
    hostname_default = vyos.get_hostname_prefered(request)
    firewall_portgroup = vyos.get_firewall_portgroup(hostname_default)
    all_instances = vyos.instance_getall_by_group(request)
    is_superuser = perms.get_is_superuser(request.user)

    template = loader.get_template('firewall/portgroup-list.html')
    context = { 
        'firewall_portgroup': firewall_portgroup,
        'hostname_default': hostname_default,
        'username': request.user, 
        'instances': all_instances,
        'is_superuser' : is_superuser,
    }   
    return HttpResponse(template.render(context, request))

@is_authenticated
def firewall_portgroup_del(request, groupname):
    hostname_default = vyos.get_hostname_prefered(request)
    vyos.set_firewall_portgroup_del(hostname_default, groupname)
    return redirect('firewall:firewall-portgroup-list')

@is_authenticated
def firewall_portgroup_add(request):
    hostname_default = vyos.get_hostname_prefered(request)
    all_instances = vyos.instance_getall_by_group(request)
    is_superuser = perms.get_is_superuser(request.user)
    netservices = network.get_services()

    if request.POST.get('name', None) != None and request.POST.get('portgroup_ports_hidden', None) != None and request.POST.get('portgroup_ports_hidden') != '':

        try:
            ports = json.loads(request.POST.get('portgroup_ports_hidden'))
        except ValueError:
            return redirect('firewall:firewall-portgroup-list')

        for port in ports:
            vyos.set_firewall_portgroup_add(hostname_default, request.POST.get('name'), port)

        if request.POST.get('description', None) != None:
            vyos.set_firewall_portgroup_description(hostname_default, request.POST.get('name'), request.POST.get('description'))

        return redirect('firewall:firewall-portgroup-list')



    template = loader.get_template('firewall/portgroup-add.html')
    context = { 
        'hostname_default': hostname_default,
        'username': request.user,        
        'instances': all_instances,
        'is_superuser' : is_superuser,
        'services_common' : netservices['common'],
        'services' : netservices['services'],
    }   
    return HttpResponse(template.render(context, request))

@is_authenticated
def firewall_portgroup_edit(request, groupname):
    hostname_default = vyos.get_hostname_prefered(request)
    all_instances = vyos.instance_getall_by_group(request)
    is_superuser = perms.get_is_superuser(request.user)
    netservices = network.get_services()
    portgroups = vyos.get_firewall_portgroup(hostname_default)
    portgroups_json = json.dumps(portgroups['port-group'][groupname], separators=(',', ':'))
    description = portgroups['port-group'][groupname]['description']

    if request.POST.get('description', None) != None:
        vyos.set_firewall_portgroup_description(hostname_default, groupname, request.POST.get('description'))

    if request.POST.get('portgroup_ports_hidden', None) != None and request.POST.get('portgroup_ports_hidden') != '':

        try:
            ports = json.loads(request.POST.get('portgroup_ports_hidden'))
        except ValueError:
            return redirect('firewall:firewall-portgroup-list')

        port_remove = []
        port_add = []
        # each port in vyos database
        for port in portgroups['port-group'][groupname]['port']:
            # vyos port not in form
            if port not in ports:
                # so mark to remove
                port_remove.append(port)

        # each port comming from form
        for port in ports:
            # form port not in vyos database
            if port not in portgroups['port-group'][groupname]['port']:
                # so mark to add
                port_add.append(port)

        # add ports to vyos database
        for port in port_add:
            vyos.set_firewall_portgroup_add(hostname_default, groupname, port)

        # remove ports to vyos database
        for port in port_remove:
            vyos.set_firewall_portgroup_delete_port(hostname_default, groupname, port)

        if request.POST.get('description', None) != None:
            vyos.set_firewall_portgroup_description(hostname_default, request.POST.get('name'), request.POST.get('description'))

        return redirect('firewall:firewall-portgroup-list')




    template = loader.get_template('firewall/portgroup-edit.html')
    context = { 
        'hostname_default': hostname_default,
        'username': request.user,        
        'instances': all_instances,
        'is_superuser' : is_superuser,
        'groupname' : groupname,
        'services_common' : netservices['common'],
        'services' : netservices['services'],
        'description' : description,
        'portgroups_json' : portgroups_json,
    }   
    return HttpResponse(template.render(context, request))


@is_authenticated
def firewall_networkgroup_list(request):
        
    hostname_default = vyos.get_hostname_prefered(request)
    firewall_networkgroup = vyos.get_firewall_networkgroup(hostname_default)
    all_instances = vyos.instance_getall_by_group(request)
    is_superuser = perms.get_is_superuser(request.user)

    template = loader.get_template('firewall/networkgroup-list.html')
    context = { 
        'firewall_networkgroup': firewall_networkgroup,
        'hostname_default': hostname_default,
        'username': request.user, 
        'instances': all_instances,
        'is_superuser' : is_superuser,
    }   
    return HttpResponse(template.render(context, request))

@is_authenticated
def firewall_networkgroup_add(request):
    hostname_default = vyos.get_hostname_prefered(request)
    all_instances = vyos.instance_getall_by_group(request)
    is_superuser = perms.get_is_superuser(request.user)

    if request.POST.get('name', None) != None and request.POST.get('network', None) != None:
        vyos.set_firewall_networkgroup_add(hostname_default, request.POST.get('name'), request.POST.get('network'))

        if request.POST.get('description', None) != None:
            vyos.set_firewall_networkgroup_description(hostname_default, request.POST.get('name'), request.POST.get('description'))

        return redirect('firewall:firewall-networkgroup-list')



    template = loader.get_template('firewall/networkgroup-add.html')
    context = { 
        'hostname_default': hostname_default,
        'username': request.user,        
        'instances': all_instances,
        'is_superuser' : is_superuser,
    }   
    return HttpResponse(template.render(context, request))

@is_authenticated
def firewall_networkgroup_del(request, groupname):
    hostname_default = vyos.get_hostname_prefered(request)
    vyos.set_firewall_networkgroup_del(hostname_default, groupname)
    return redirect('firewall:firewall-networkgroup-list')

@is_authenticated
def firewall_addressgroup_list(request):
        
    hostname_default = vyos.get_hostname_prefered(request)
    firewall_addressgroup = vyos.get_firewall_addressgroup(hostname_default)
    all_instances = vyos.instance_getall_by_group(request)
    is_superuser = perms.get_is_superuser(request.user)

    template = loader.get_template('firewall/addressgroup-list.html')
    context = { 
        'firewall_addressgroup': firewall_addressgroup,
        'hostname_default': hostname_default,
        'username': request.user,        
        'instances': all_instances,
        'is_superuser' : is_superuser,
    }   
    return HttpResponse(template.render(context, request))

@is_authenticated
def firewall_addressgroup_add(request):
        
    hostname_default = vyos.get_hostname_prefered(request)
    all_instances = vyos.instance_getall_by_group(request)
    is_superuser = perms.get_is_superuser(request.user)

    if request.POST.get('addresstype', None) == "single" and request.POST.get('name', None) != None and request.POST.get('address', None) != None:
        vyos.set_firewall_addressgroup_add(hostname_default, request.POST.get('name'), request.POST.get('address'))

        if request.POST.get('description', None) != None:
            vyos.set_firewall_addressgroup_description(hostname_default, request.POST.get('name'), request.POST.get('description'))

        return redirect('firewall:firewall-addressgroup-list')
    elif request.POST.get('addresstype', None) == "range" and request.POST.get('name', None) != None and request.POST.get('address-start', None) != None and request.POST.get('address-end', None) != None:
        vyos.set_firewall_addressgroup_rangeadd(hostname_default, request.POST.get('name'), request.POST.get('address-start'), request.POST.get('address-end'))

        if request.POST.get('description', None) != None:
            vyos.set_firewall_addressgroup_description(hostname_default, request.POST.get('name'), request.POST.get('description'))

        return redirect('firewall:firewall-addressgroup-list')



    template = loader.get_template('firewall/addressgroup-add.html')
    context = { 
        'hostname_default': hostname_default,
        'username': request.user,        
        'instances': all_instances,
        'is_superuser' : is_superuser,
    }   
    return HttpResponse(template.render(context, request))

@is_authenticated
def firewall_addressgroup_del(request, groupname):
    hostname_default = vyos.get_hostname_prefered(request)
    vyos.set_firewall_addressgroup_del(hostname_default, groupname)
    return redirect('firewall:firewall-addressgroup-list')

@is_authenticated
def firewall_addressgroup_desc(request, groupname):
    hostname_default = vyos.get_hostname_prefered(request)
    firewall_addressgroup = vyos.get_firewall_addressgroup_one(hostname_default, groupname)
    all_instances = vyos.instance_getall_by_group(request)
    is_superuser = perms.get_is_superuser(request.user)

    if request.POST.get('description', None) != None:
        vyos.set_firewall_addressgroup_description(hostname_default, groupname, request.POST.get('description'))
        return redirect('firewall:firewall-addressgroup-list')


    template = loader.get_template('firewall/addressgroup-desc.html')
    context = { 
        'firewall_addressgroup': firewall_addressgroup,
        'hostname_default': hostname_default,
        'username': request.user,        
        'instances': all_instances,
        'is_superuser' : is_superuser,
        'groupname': groupname,
    }   
    return HttpResponse(template.render(context, request))

@is_authenticated
def firewall_networkgroup_desc(request, groupname):
    hostname_default = vyos.get_hostname_prefered(request)
    firewall_networkgroup = vyos.get_firewall_networkgroup_one(hostname_default, groupname)
    all_instances = vyos.instance_getall_by_group(request)
    is_superuser = perms.get_is_superuser(request.user)

    if request.POST.get('description', None) != None:
        vyos.set_firewall_networkgroup_description(hostname_default, groupname, request.POST.get('description'))
        return redirect('firewall:firewall-networkgroup-list')

    template = loader.get_template('firewall/networkgroup-desc.html')
    context = { 
        'firewall_networkgroup': firewall_networkgroup,
        'hostname_default': hostname_default,
        'username': request.user,        
        'instances': all_instances,
        'is_superuser' : is_superuser,
        'groupname': groupname,
    }   
    return HttpResponse(template.render(context, request))

@is_authenticated
def firewall_config(request, firewall_name):  
    #interfaces = vyos.get_interfaces()
    all_instances = vyos.instance_getall()
    hostname_default = vyos.get_hostname_prefered(request)
    is_superuser = perms.get_is_superuser(request.user)
    
    firewall = vyos.get_firewall(hostname_default, firewall_name)
    

    template = loader.get_template('firewall/show.html')
    context = { 
        #'interfaces': interfaces,
        'instances': all_instances,
        'hostname_default': hostname_default,
        'firewall':  firewall,
        'firewall_name': firewall_name,
        'username': request.user,
        'is_superuser' : is_superuser,
    }   
    return HttpResponse(template.render(context, request))

@is_authenticated
def firewall_global(request):
   
    #interfaces = vyos.get_interfaces()
    all_instances = vyos.instance_getall()
    hostname_default = vyos.get_hostname_prefered(request)

    if int(request.POST.get('allping', 0)) == 1:
        vyos.set_firewall_allping_enable(hostname_default)
    else:
        vyos.set_firewall_allping_disable(hostname_default)

    if int(request.POST.get('syncookies', 0)) == 1:
        vyos.set_firewall_syncookies_enable(hostname_default)
    else:
        vyos.set_firewall_syncookies_disable(hostname_default)

    
    return redirect('firewall:firewall-list')

@is_authenticated
def firewall_remove(request, firewall_name):
       
    #interfaces = vyos.get_interfaces()
    all_instances = vyos.instance_getall()
    hostname_default = vyos.get_hostname_prefered(request)

    firewall = vyos.delete_firewall(hostname_default, firewall_name)
    
    return redirect('firewall:firewall-list')

@is_authenticated
def firewall_edit(request, firewall_name):
   
    #interfaces = vyos.get_interfaces()
    all_instances = vyos.instance_getall()
    hostname_default = vyos.get_hostname_prefered(request)
    firewall = vyos.get_firewall(hostname_default, firewall_name)
    firewall['defaultaction'] = firewall['default-action']
    is_superuser = perms.get_is_superuser(request.user)

    changed = False
    if 'description' in request.POST:
        cmd = {"op": "set", "path": ["firewall", "name", firewall_name, "description", request.POST['description']]}
        result2 = vyos.set_config(hostname_default, cmd)
        print(result2)
        changed = True

    if 'action' in request.POST:
        cmd = {"op": "set", "path": ["firewall", "name", firewall_name, "default-action", request.POST['action']]}
        result3 = vyos.set_config(hostname_default, cmd)
        print(result3)
        changed = True

    if changed == True:
        return redirect('firewall:firewall-list')

    template = loader.get_template('firewall/edit.html')
    context = { 
        #'interfaces': interfaces,
        'instances': all_instances,
        'hostname_default': hostname_default,
        'firewall_name': firewall_name,
        'firewall': firewall,
        'username': request.user,
        'is_superuser' : is_superuser,
    }   
    return HttpResponse(template.render(context, request))