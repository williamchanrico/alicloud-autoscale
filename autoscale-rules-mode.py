#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Automate the process of changing/creating auto-scaling rules based on config file
Each config file represent a mode (e.g. 'normal.yaml', 'grammy.yaml')
Default mode is 'normal', use '--mode' flag to specify a mode

Please make sure that every scaling rules follow the same 
naming convention: app-name-upscale/app-name-downscale

usage: autoscale-trigger-mode.py [-h] [-m MODE] [-l LIMIT] [-s] [-v]
                                 [--version]
                                 access_key_id access_key_secret region_id

positional arguments:
  access_key_id         Accesskey ID for aliyun account
  access_key_secret     AccessKey secret for aliyun account
  region_id             ID of the region where the service is called

optional arguments:
  -h, --help            show this help message and exit
  -m MODE, --mode MODE  Autoscale event-trigger task mode config
  -l LIMIT, --limit LIMIT
                        Limit target rules
  -s, --skip-sync       Skip synching cached_rules.yaml for faster runtime if
                        you're sure that no rules has been changed in aliyun
  -v, --verbose         Verbosity (-v, -vv, etc)
  --version             show program's version number and exit
"""

__version__ = "0.1.1"

import os
import sys
import time
import yaml
import argparse
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.acs_exception.exceptions import ClientException
from aliyunsdkcore.acs_exception.exceptions import ServerException
from aliyunsdkess.request.v20140828 import DescribeScalingRulesRequest
from aliyunsdkess.request.v20140828 import ModifyScalingRuleRequest
from aliyunsdkess.request.v20140828 import CreateScalingRuleRequest
from aliyunsdkess.request.v20140828 import DescribeScalingGroupsRequest

# Global internal variables
_mode = ""
_verbose = False
_client = None
_config = None
_current_rules = {}
_skip_sync = False
_limit = []
_scaling_groups = {}

def init(args):
    """ Initialization """

    global _mode, _verbose, _client, _skip_sync, _limit

    # Initialize necessary variables
    _mode = args.mode
    _verbose = args.verbose
    _skip_sync = args.skip_sync
    _limit = args.limit.split(',')
    if _limit[0] == '':
        _limit = None

    access_key_id = args.access_key_id
    access_key_secret = args.access_key_secret
    region_id = args.region_id
    
    # Initialize AcsClient obj to consume the core API
    print "Initializing API client object using the configured access key"
    _client = AcsClient(
        access_key_id,
        access_key_secret,
        region_id
    )

    # Load current scaling groups that exist in aliyun
    print "Loading scaling groups information from aliyun"
    load_scaling_groups()

    # Load selected mode config file
    print "Loading selected mode config from config/" + _mode + ".yaml"
    load_mode_config()

    # Load current rules that are being used in aliyun
    load_current_rules()

    print "There are total of {} scaling rules detected".format(len(_current_rules))

def load_mode_config():
    global _config

    __location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
    try:
        with open(os.path.join(__location__, 'config/' + _mode + '.yaml')) as file:
            _config = yaml.safe_load(file)
        
        # Check config for possible typo
        # Current check:
        #   1. Downscale rule must have negative value (this is how aliyun differentiate 'increase by' with 'decrease by')
        
        # Check #1
        for a in _config:
            if rule_type(a) == 0 and _config[a]['AdjustmentValue'] >= 0:
                print "ERROR {}: Downscale rule must have a negative 'AdjustmentValue', stopping script".format(a)
                sys.exit(1)
    except IOError:
        print _mode, "Config file not found"
        print sys.exc_info()
        sys.exit(1)

def load_current_rules():
    global _current_rules

    __location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
    if _skip_sync is True:
        print "Loading current rules from cached_rules.yaml (not using real-time data from aliyun)"
        try:
            with open(os.path.join(__location__, 'cached_rules.yaml')) as file:
                _current_rules = yaml.safe_load(file)
        except:
            print "The file cached_rules.yaml not found, syncing from aliyun anyway"
            _current_rules = reconstruct_current_rules_cache()
    else:
        print "Loading current rules from aliyun (cached_rules.yaml is ignored)"
        _current_rules = reconstruct_current_rules_cache()
    
def reconstruct_current_rules_cache():
    """
        Get all scaling rules in aliyun and construct a cache file
        Will also return a dictionary file containing:
            galadriel-banner-upscale:
                AdjustmentType: PercentChangeInCapacity
                AdjustmentValue: 50
                Cooldown: 60
                ScalingGroupId: asg-blabla
                ScalingRuleAri: ari:acs:ess:ap-southeast-1:12345:scalingrule/asr-blabla
                ScalingRuleId: asr-blabla
                ScalingRuleName: galadriel-banner-upscale
            go-accounts-downscale:
                AdjustmentType: PercentChangeInCapacity
                AdjustmentValue: 20
                Cooldown: 60
                ScalingGroupId: asg-blabla
                ScalingRuleAri: ari:acs:ess:ap-southeast-1:12345:scalingrule/asr-blabla
                ScalingRuleId: asr-blabla
                ScalingRuleName: go-accounts-downscale
            ...
    """
    page_size = 50
    page_number = 1

    req = DescribeScalingRulesRequest.DescribeScalingRulesRequest()
    req.set_PageSize(page_size)
    req.set_PageNumber(page_number)
    
    try:
        resp_body = _client.do_action_with_exception(req)
    except ClientException:
        print "ERROR getting current rules from aliyun: API connection issue, please try again"
        print sys.exc_info()
        sys.exit()
        
    resp_yaml = yaml.safe_load(resp_body)
    total_count = int(resp_yaml['TotalCount'])
    
    rules = {}
    for a in resp_yaml['ScalingRules']['ScalingRule']:
        rules[a['ScalingRuleName']] = a
    
    while total_count > 0:
        total_count -= page_size
        page_number += 1

        if total_count > 0:
            time.sleep(1)
            req.set_PageNumber(page_number)
            try:
                resp_body = _client.do_action_with_exception(req)
            except ClientException:
                print "ERROR getting current rules from aliyun: API connection issue, please try again"
                print sys.exc_info()
                sys.exit()
            resp_yaml = yaml.safe_load(resp_body)
            for a in resp_yaml['ScalingRules']['ScalingRule']:
                rules[a['ScalingRuleName']] = a
                
    # Saving current rules from aliyun into cached_rules.yaml
    dump_current_rules(rules, 'cached_rules.yaml')

    return rules

def rule_type(rule_name):
    """ Returns 1 for upscale rule, 0 for downscale rule, -1 for unrecognized rule """
    # TODO: Use enumeration type to support more type in the future (in case we want more than just an upscale or downscale rule)

    if rule_name.find("-upscale") != -1:
        return 1
    elif rule_name.find("-downscale") != -1:
        return 0
    return -1

def load_scaling_groups():
    """
        Load all existing scaling group in aliyun and store in global _scaling_groups
    """
    global _scaling_groups

    page_size = 50
    page_number = 1

    req = DescribeScalingGroupsRequest.DescribeScalingGroupsRequest()
    req.set_PageSize(page_size)
    req.set_PageNumber(page_number)
    
    try:
        resp_body = _client.do_action_with_exception(req)
    except ClientException:
        print "ERROR loading scaling groups from aliyun: API connection issue, please try again"
        print sys.exc_info()
        sys.exit()
    resp_yaml = yaml.safe_load(resp_body)
    total_count = int(resp_yaml['TotalCount'])
    
    _scaling_groups = {}
    for a in resp_yaml['ScalingGroups']['ScalingGroup']:
        _scaling_groups[a['ScalingGroupName']] = a['ScalingGroupId']
    
    while total_count > 0:
        total_count -= page_size
        page_number += 1

        if total_count > 0:
            time.sleep(1)
            req.set_PageNumber(page_number)
            try:
                resp_body = _client.do_action_with_exception(req)
            except ClientException:
                print "ERROR loading scaling groups from aliyun: API connection issue, please try again"
                print sys.exc_info()
                sys.exit()
            resp_yaml = yaml.safe_load(resp_body)
            for a in resp_yaml['ScalingGroups']['ScalingGroup']:
                _scaling_groups[a['ScalingGroupName']] = a['ScalingGroupId']
        
def create_and_attach_scaling_rule(scaling_rule_name, scaling_group_name):
    if scaling_group_name not in _scaling_groups:
        print "WARNING '{}': Scaling group doesn't exists".format(scaling_group_name)
        return

    new_rule = get_rule(scaling_rule_name)
    if not new_rule:
        return
    
    try:
        # Create request obj
        req = CreateScalingRuleRequest.CreateScalingRuleRequest()

        # Setting request parameters
        # Necessary: Yes, to specify the rule and which scaling group to attach the rule to
        req.set_ScalingGroupId(str(_scaling_groups[scaling_group_name]))
        req.set_AdjustmentType(new_rule['AdjustmentType'])
        req.set_AdjustmentValue(new_rule['AdjustmentValue'])

        # Necessary: No, to set other values we want
        req.set_Cooldown(new_rule['Cooldown'])
        req.set_ScalingRuleName(scaling_rule_name)

        # Send the modify request
        _client.do_action_with_exception(req)
    except ClientException:
        print "ERROR '{}': API connection issue, please try again".format(scaling_rule_name)
        print sys.exc_info()
        print ""
    except:
        print "ERROR '{}'@'{}': {}".format(scaling_rule_name, scaling_group_name, sys.exc_info())

    print "CHANGED '{}': Created scaling rule and attached it to scaling group '{}'".format(scaling_rule_name, scaling_group_name)

def get_rule(scaling_rule_name):
    try:
        # Getting rule from loaded config file
        new_rule = _config[scaling_rule_name]
    except KeyError:
        if _verbose:
            print scaling_rule_name, "config is not set in '{}.yaml', will proceed using default config".format(_mode)
        if rule_type(scaling_rule_name) == 1:
            new_rule = _config['default-upscale']
        elif rule_type(scaling_rule_name) == 0:
            new_rule = _config['default-downscale']
        else:
            print "SKIPPED '{}': Can't determine whether that's an upscale or downscale rule".format(scaling_rule_name)
            return None
    return new_rule

def modify_scaling_rule(scaling_rule_name):
    new_rule = get_rule(scaling_rule_name)
    if not new_rule:
        return

    # Compare old and new rule, skip is nothing was changed
    skip = True
    current_rule = _current_rules[scaling_rule_name]
    for k, v in new_rule.iteritems():
        try:
            if current_rule[k] != v:
                skip = False
                break
        except KeyError:
            skip = False
            break
    if skip is True:
        print "SKIPPED '{}': No difference between the current and the new rule".format(scaling_rule_name)
        return

    try:
        # Create request obj
        req = ModifyScalingRuleRequest.ModifyScalingRuleRequest()

        # Setting request parameters
        # Necessary: Yes, to specify which scaling rules in aliyun that we're changing
        req.set_ScalingRuleId(str(_current_rules[scaling_rule_name]['ScalingRuleId']))

        # Necessary: No, to set new values we want to replace
        req.set_AdjustmentType(new_rule['AdjustmentType'])
        req.set_AdjustmentValue(new_rule['AdjustmentValue'])
        req.set_Cooldown(new_rule['Cooldown'])

        # Send the modify request
        _client.do_action_with_exception(req)
    except KeyError:
        global _skip_sync
        if _skip_sync is True:
            print "WARNING '{}': Scaling rule does not exist, try running the script without --skip-sync flag".format(scaling_rule_name)
        else:
            print "WARNING '{}': Scaling rule does not exist in aliyun, have you created the scaling rule in aliyun?".format(scaling_rule_name)
    except ClientException:
        print "ERROR '{}': API connection issue, please try again".format(scaling_rule_name)
        print sys.exc_info()
        print ""
    except:
        print "ERROR '{}': {}".format(scaling_rule_name, sys.exc_info())
    
    print "CHANGED '{}': Successfully modified the scaling rule".format(scaling_rule_name)

    # Apply changes into _current_rules too so we can cache it
    _current_rules[scaling_rule_name]['AdjustmentType'] = new_rule['AdjustmentType']
    _current_rules[scaling_rule_name]['AdjustmentValue'] = new_rule['AdjustmentValue']
    _current_rules[scaling_rule_name]['Cooldown'] = new_rule['Cooldown']

def dump_current_rules(rules, cache_path):
    try:
        __location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
        with open(os.path.join(__location__, cache_path), "w") as file:
            yaml.dump(rules, file, default_flow_style=False)
    except:
        print "Error dumping current rules into cached_rules.yaml", sys.exc_info()

def determine_scaling_group(rule_name):
    is_upscale = rule_type(rule_name)
    if is_upscale == -1:
        return None

    suffix_idx = -1
    if is_upscale == 1:
        suffix_idx = rule_name.find("-upscale")
        return rule_name[:suffix_idx]
    else:
        suffix_idx = rule_name.find("-downscale")
        return rule_name[:suffix_idx]

def query_yes_no(msg):
    # raw_input returns the empty string for "enter"
    yes = {'yes','y', 'ye', ''}
    no = {'no','n'}

    while True:
        print msg, "[Y/n]",
        choice = raw_input().lower()
        if choice in yes:
            return True
        elif choice in no:
            return False
        else:
            sys.stdout.write("Please respond with 'yes' or 'no'")

def main(args):
    """ Main entry point """
    init(args)

    # Start modifying rules
    print ""
    processed_mode_rules = {}
    for a in _config:
        if a.find("default") == -1:
            if _limit and a in _limit:
                processed_mode_rules[a] = False
            elif not _limit:
                processed_mode_rules[a] = False                

    if _limit:
        for a in _limit:
            modify_scaling_rule(a)
            processed_mode_rules[a] = True
    else:
        for a in _current_rules:
            modify_scaling_rule(a)
            processed_mode_rules[a] = True
    # Finish modifying rules
    
    # Process rules that wasn't found in aliyun, but are listed in mode config file
    print "\nThese rules are not found in aliyun:"
    not_found_rules = False
    scaling_groups = {}
    for a in processed_mode_rules:
        if not processed_mode_rules[a]:
            rule_scaling_group = determine_scaling_group(a)
            if rule_scaling_group != None:
                print "{}: should belong to ScalingGroup={}".format(a, rule_scaling_group)
                scaling_groups[a] = rule_scaling_group
                not_found_rules = True
            else:
                print "{}: can't determine its ScalingGroup, please check the naming convention (appname-upscale/appname-downscale)".format(a)
                processed_mode_rules[a] = True

    # Start creating rules if the scaling group exists and can be determined (only if user wants to)
    if not_found_rules:
        add_new_rules = query_yes_no("\nDo you want to create those rules in aliyun?")
        if add_new_rules:
            for a in processed_mode_rules:
                if not processed_mode_rules[a]:                
                    create_and_attach_scaling_rule(a, scaling_groups[a])
        else:
            print "Ignoring those rules"
    print ""

    # Dump modified _current_rules into cached_rules.yaml
    print "Caching all changed rules into cached_rules.yaml"
    if not_found_rules and add_new_rules:
        reconstruct_current_rules_cache()
    else:
        dump_current_rules(_current_rules, 'cached_rules.yaml')

if __name__ == "__main__":
    """ This is executed when run from the command line """
    parser = argparse.ArgumentParser()

    # Access Key
    parser.add_argument("access_key_id", help="Accesskey ID for aliyun account")
    parser.add_argument("access_key_secret", help="AccessKey secret for aliyun account")
    parser.add_argument("region_id", help="ID of the region where the service is called")
    
    # Optional argument which requires a parameter (eg. -m grammy)
    parser.add_argument(
        "-m",
        "--mode",
        action="store",
        dest="mode",
        default="normal",
        help="Autoscale event-trigger task mode config")
    
    # Optional argument which requires a parameter (eg. -l go-testapp-upscale,go-testapp-downscale)
    parser.add_argument(
        "-l",
        "--limit",
        action="store",
        dest="limit",
        default="",
        help="Limit target rules")

    # Optional flag, decide whether to sync the cached_rules.yaml (faster if skipped, but only skip if you know what you're doing)
    parser.add_argument(
        "-s",
        "--skip-sync",
        dest="skip_sync",
        action="store_true",
        help="Skip synching cached_rules.yaml for faster runtime if you're sure that no rules has been changed in aliyun"
    )
    
    # Optional verbosity counter (eg. -v, -vv, -vvv, etc.)
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Verbosity (-v, -vv, etc)")

    # Specify output of "--version"
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s (version {version})".format(version=__version__))

    args = parser.parse_args()
    main(args)
