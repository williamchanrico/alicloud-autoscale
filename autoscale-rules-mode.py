#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
    Automate the process of changing/creating auto-scaling rules based on config file
    Each config directory represents a mode (e.g. './config/normal/*.yaml', './config/grammy/*.yaml')
    Default mode is 'normal', use '--mode' flag to specify a mode

    Please make sure that every scaling rules follow the same 
    naming convention: app-name-upscale/app-name-downscale

    usage: autoscale-rules-mode.py [-h] [-m MODE] [-l LIMIT] [-s] [-v] [-n]
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
    -n, --noconfirm       Skip interactive prompts (yes to all)
    --version             show program's version number and exit
"""

__version__ = "0.2.0"

import os
import glob
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
from aliyunsdkess.request.v20140828 import DescribeAlarmsRequest
from aliyunsdkess.request.v20140828 import CreateAlarmRequest
from aliyunsdkess.request.v20140828 import ModifyAlarmRequest
from aliyunsdkess.request.v20140828 import DeleteAlarmRequest
from aliyunsdkess.request.v20140828 import DisableAlarmRequest

# Global internal variables
_mode = ""
_verbose = False
_client = None
_noconfirm = False
_config = {}
_current_rules = {}
_skip_sync = False
_limit = []
_scaling_groups = {}
_event_trigger_tasks = {}

def init(args):
    """ Initialization """
    # Initialize necessary variables
    global _mode, _verbose, _client, _skip_sync, _limit, _noconfirm
    _mode = args.mode
    _verbose = args.verbose
    _skip_sync = args.skip_sync
    _noconfirm = args.noconfirm
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

    # Load selected mode config file
    load_mode_config()
    
    # Load current scaling groups that exist in aliyun
    load_scaling_groups()

    # Load current rules that are being used in aliyun
    load_current_rules()

    # Load current event trigger tasks that exist in aliyun
    load_event_trigger_tasks()

    print "There are total of {} scaling rules detected".format(len(_current_rules))

def load_event_trigger_tasks():
    """ Load all existing event-trigger tasks in aliyun and store in global _scaling_groups """
    global _event_trigger_tasks

    print "Loading event-trigger tasks information from aliyun"

    page_size = 50
    page_number = 1

    req = DescribeAlarmsRequest.DescribeAlarmsRequest()
    req.set_PageSize(page_size)
    req.set_PageNumber(page_number)
    
    try:
        resp_body = _client.do_action_with_exception(req)
    except ClientException:
        print "ERROR loading event-trigger tasks from aliyun: API connection issue, please try again"
        print sys.exc_value
        sys.exit()
    resp_yaml = yaml.safe_load(resp_body)
    total_count = int(resp_yaml['TotalCount'])
    
    _event_trigger_tasks = {}
    for a in resp_yaml['AlarmList']['Alarm']:
        a['TriggerAfter'] = a['EvaluationCount']
        a['Condition'] = a['Statistics']
        a['MetricItem'] = a['MetricName']
        a['RefreshCycleSeconds'] = a['Period']
        _event_trigger_tasks[a['Name']] = a
    
    while total_count > 0:
        total_count -= page_size
        page_number += 1

        if total_count > 0:
            time.sleep(1)
            req.set_PageNumber(page_number)
            try:
                resp_body = _client.do_action_with_exception(req)
            except ClientException:
                print "ERROR loading event-trigger tasks from aliyun: API connection issue, please try again"
                print sys.exc_value
                sys.exit()
            resp_yaml = yaml.safe_load(resp_body)
            for a in resp_yaml['AlarmList']['Alarm']:
                a['TriggerAfter'] = a['EvaluationCount']
                a['Condition'] = a['Statistics']
                a['MetricItem'] = a['MetricName']
                a['RefreshCycleSeconds'] = a['Period']
                _event_trigger_tasks[a['Name']] = a

def load_scaling_groups():
    """ Load all existing scaling group in aliyun and store in global _scaling_groups """
    global _scaling_groups

    print "Loading scaling groups information from aliyun"

    page_size = 50
    page_number = 1

    req = DescribeScalingGroupsRequest.DescribeScalingGroupsRequest()
    req.set_PageSize(page_size)
    req.set_PageNumber(page_number)
    
    try:
        resp_body = _client.do_action_with_exception(req)
    except ClientException:
        print "ERROR loading scaling groups from aliyun: API connection issue, please try again"
        print sys.exc_value
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
                print sys.exc_value
                sys.exit()
            resp_yaml = yaml.safe_load(resp_body)
            for a in resp_yaml['ScalingGroups']['ScalingGroup']:
                _scaling_groups[a['ScalingGroupName']] = a['ScalingGroupId']

def load_mode_config():
    """ Load mode config from the selected mode yaml file into global _config variable """
    global _config

    print "Loading selected mode config from config/" + _mode + "/*.yaml"
    __location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
    config_path = os.path.join(__location__, 'config/' + _mode + '/*.yaml')
    try:
        for a in glob.glob(config_path):
            with open(a) as file:
                _partial_config = yaml.safe_load(file)
                for b in _partial_config:
                    _config[b] = _partial_config[b]
        
        # Check config for possible typo
        # Current checks:
        #   1. Downscale rule must have negative value (this is how aliyun differentiate 'Increase by' with 'Decrease by')
        
        # Check #1
        for a in _config:
            if rule_type(a) == 0 and _config[a]['AdjustmentValue'] >= 0:
                print "ERROR {}: Downscale rule must have a negative 'AdjustmentValue', stopping script".format(a)
                sys.exit(1)
    except IOError:
        print _mode, "Config file not found"
        print sys.exc_value
        sys.exit(1)

def load_current_rules():
    """ Load current rules from aliyun or cached_rules.yaml file into global _current_rules variable """
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
        print sys.exc_value
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
                print sys.exc_value
                sys.exit()
            resp_yaml = yaml.safe_load(resp_body)
            for a in resp_yaml['ScalingRules']['ScalingRule']:
                rules[a['ScalingRuleName']] = a
                
    # Saving current rules from aliyun into cached_rules.yaml
    dump_current_rules(rules, 'cached_rules.yaml')

    return rules

def modify_event_trigger_task(scaling_rule_name):
    # WEIRD ModifyAlarmRequest can't modify most attributes, 
    # wait till aliyun dev update their API
    
    new_rule = get_rule(scaling_rule_name)
    if not new_rule:
        return False

    # Compare old and new rule, skip is nothing was changed
    skip = True
    current_rule = _event_trigger_tasks[scaling_rule_name]
    event_trigger_task_attr = ["MetricItem", "Condition", "ComparisonOperator", "Threshold", "TriggerAfter", "RefreshCycleSeconds"]
    for a in event_trigger_task_attr:
        try:
            if new_rule[a] != current_rule[a]:
                skip = False
                break
        except KeyError:
            skip = False
            break

    if skip is True:
        print "SKIPPED '{}': No difference between the current and the new event trigger task rule".format(scaling_rule_name)
        return True
    
    try:
        # Create request obj
        req = ModifyAlarmRequest.ModifyAlarmRequest()

        # Setting request parameters
        # Necessary: Yes, to specify the rule and which scaling group to attach the rule to
        req.set_AlarmTaskId(_event_trigger_tasks[scaling_rule_name]["AlarmTaskId"])
        req.set_Name(scaling_rule_name)
        # req.set_MetricName(str(new_rule["MetricItem"]))
        # req.set_Statistics(str(new_rule["Condition"]))
        # req.set_ComparisionOperator(str(new_rule["ComparisonOperator"]))
        # req.set_Threshold(new_rule["Threshold"])
        alarm_actions = []
        alarm_actions.append(str(_current_rules[scaling_rule_name]["ScalingRuleAri"]))
        req.set_AlarmActions(alarm_actions)

        # Necessary: No, to set other values we want
        # req.set_EvaluationCount(new_rule["TriggerAfter"])
    
        # Send the modify request
        _client.do_action_with_exception(req)

        print "CHANGED '{}': Successfully modified event trigger task".format(scaling_rule_name)

        return True
    except ClientException:
        print "ERROR '{}': API connection issue, please try again".format(scaling_rule_name)
        print sys.exc_value
        print ""
        return False
    except:
        print "ERROR in modifying event trigger task {}: {}".format(scaling_rule_name, sys.exc_info())
        return False

def delete_event_trigger_task(scaling_rule_name):
    """
        Delete event trigger task in aliyun
        Returns the existance of the task in aliyun
        If deleted, returns True, if don't exists in the first place, also return True,
        otherwise, returns False (meaning the task still exists in aliyun)
    """
    # Check if the task already exists in aliyun
    existed = False
    try:
        current_rule = _event_trigger_tasks[scaling_rule_name]
        existed = True
    except KeyError:
        existed = False
    
    if not existed:
        if _verbose:
            print "ERROR '{}': Event trigger task don't exists, can't delete it".format(scaling_rule_name)
        return True

    try:
        req = DeleteAlarmRequest.DeleteAlarmRequest()

        req.set_AlarmTaskId(str(current_rule['AlarmTaskId']))

        _client.do_action_with_exception(req)
        
        print "CHANGED '{}': Deleted event trigger task".format(scaling_rule_name)

        return True
    except ClientException:
        print "ERROR '{}': API connection issue, please try again".format(scaling_rule_name)
        print sys.exc_value
        print ""
        return False
    except:
        print "ERROR in deleting event trigger task {}: {}".format(scaling_rule_name, sys.exc_info())
        return False

def disable_event_trigger_task(event_trigger_task_id):
    try:
        req = DisableAlarmRequest.DisableAlarmRequest()

        req.set_AlarmTaskId(str(event_trigger_task_id))

        _client.do_action_with_exception(req)
        
        print "CHANGED: Disabled the event trigger task according to the old one"

        return True
    except ClientException:
        print "ERROR '{}': API connection issue, please try again".format(event_trigger_task_id)
        print sys.exc_value
        print ""
        return False
    except:
        print "ERROR in disabling event trigger task {}: {}".format(event_trigger_task_id, sys.exc_info())
        return False

def create_event_trigger_task(scaling_rule_name):
    """
        Because aliyun API doesn't support modifying an event trigger task,
        we will do it this way, there are 2 scenarios:
            1. Creating an existing task in aliyun, 
                we check if the attributes is different,
                if they're the same, we skip it,
                if they differ, we use the delete API to delete it after the new one has been created
                creating the new event trigger task
            2. Creating a new one, proceed as usual
    """
    new_rule = get_rule(scaling_rule_name)
    if not new_rule:
        return False

    # Check if the task already exists in aliyun
    existed = False
    try:
        current_rule = _event_trigger_tasks[scaling_rule_name]
        existed = True
    except KeyError:
        existed = False

    # So if the task exists, compare old and new rule, skip is nothing has changed
    skip = True
    delete_after = False
    enable = True
    event_trigger_task_attr = ["MetricItem", "Condition", "ComparisonOperator", "Threshold", "TriggerAfter", "RefreshCycleSeconds"]
    if existed:
        try:
            if len(current_rule["alarmActions"]["alarmAction"]) == 0 or current_rule["bypass_skip"]:
                skip = False
        except KeyError:
            pass

        for a in event_trigger_task_attr:
            try:
                if new_rule[a] != current_rule[a]:
                    skip = False
                    break
            except KeyError:
                skip = False
                break
        # The rules differ, we have to remember to delete the existing rule after creating a new one
        if not skip:
            if not current_rule["Enable"]:
                enable = False
            delete_after = True
    else:
        skip = False

    if skip is True:
        print "SKIPPED '{}': No difference between the current and the new event trigger task rule".format(scaling_rule_name)
        return True

    # Finally, if skip is False, then we f'ing do it
    try:
        # Create request obj
        req = CreateAlarmRequest.CreateAlarmRequest()

        # Setting request parameters
        # Necessary: Yes, to specify the rule and which scaling group to attach the rule to
        req.set_Name(scaling_rule_name)
        req.set_ScalingGroupId(_current_rules[scaling_rule_name]["ScalingGroupId"])
        req.set_MetricName(str(new_rule["MetricItem"]))
        req.set_Statistics(str(new_rule["Condition"]))
        req.set_ComparisonOperator(str(new_rule["ComparisonOperator"]))
        req.set_Threshold(new_rule["Threshold"])
        alarm_actions = []
        alarm_actions.append(str(_current_rules[scaling_rule_name]["ScalingRuleAri"]))
        req.set_AlarmActions(alarm_actions)

        # Necessary: No, to set other values we want
        req.set_EvaluationCount(new_rule["TriggerAfter"])
        req.set_Period(new_rule["RefreshCycleSeconds"])
    
        # Send the modify request
        resp_body = _client.do_action_with_exception(req)
        resp_yaml = yaml.safe_load(resp_body)

        print "CHANGED '{}': Successfully created event trigger task".format(scaling_rule_name)
        
        # Existing task was disabled, so we also disable the newly created one
        if not enable:
            if not disable_event_trigger_task(resp_yaml["AlarmTaskId"]):
                print "ERROR '{}': Failed to disable newly created task (old task was disabled), send help, disable them manually".format(scaling_rule_name)

        # We delete the old one to prevent duplicate task in aliyun
        if delete_after:
            print "Deleting old '{}' event trigger task".format(scaling_rule_name)
            if not delete_event_trigger_task(scaling_rule_name):
                print "ERROR '{}': Failed to delete old task, there will be duplicate task, send help, delete them manually".format(scaling_rule_name)
                return False

        return True
    except ClientException:
        print "ERROR '{}': API connection issue, please try again".format(scaling_rule_name)
        print sys.exc_value
        print ""
        return False
    except:
        print "ERROR in creating event trigger task {}: {}".format(scaling_rule_name, sys.exc_info())
        return False

def rule_type(rule_name):
    """ Returns 1 for upscale rule, 0 for downscale rule, -1 for unrecognized rule """
    # TODO: Use enumeration type to support more type in the future (in case we want more than just an upscale or downscale rule)
    if rule_name.find("-upscale") != -1:
        return 1
    elif rule_name.find("-downscale") != -1:
        return 0
    return -1
        
def create_and_attach_scaling_rule(scaling_rule_name, scaling_group_name):
    """ Create and attach a scaling rule into detected scaling group (only if the scaling group exists in aliyun) """
    new_rule = get_rule(scaling_rule_name)
    if not new_rule:
        return False
    
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

        print "CHANGED '{}': Created scaling rule and attached it to scaling group '{}'".format(scaling_rule_name, scaling_group_name)

        return True
    except ClientException:
        print "ERROR '{}': API connection issue, please try again".format(scaling_rule_name)
        print sys.exc_value
        print ""
        return False
    except:
        print "ERROR '{}'@'{}': {}".format(scaling_rule_name, scaling_group_name, sys.exc_info)
        return False

def get_rule(scaling_rule_name):
    """ Safely retrieve a specified rule """
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
    """ Modify a scaling rule in aliyun. Will skip if no value has been changed """
    new_rule = get_rule(scaling_rule_name)
    if not new_rule:
        return False

    # Compare old and new rule, skip is nothing was changed
    skip = True
    current_rule = _current_rules[scaling_rule_name]
    scaling_rule_attr = ["AdjustmentType", "AdjustmentValue", "Cooldown"]
    for a in scaling_rule_attr:
        try:
            if new_rule[a] != current_rule[a]:
                skip = False
                break
        except KeyError:
            skip = False
            break

    if skip is True:
        print "SKIPPED '{}': No difference between the current and the new rule".format(scaling_rule_name)
        return True

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

        # Apply changes into _current_rules too so we can cache it
        _current_rules[scaling_rule_name]['AdjustmentType'] = new_rule['AdjustmentType']
        _current_rules[scaling_rule_name]['AdjustmentValue'] = new_rule['AdjustmentValue']
        _current_rules[scaling_rule_name]['Cooldown'] = new_rule['Cooldown']
        
        print "CHANGED '{}': Successfully modified the scaling rule".format(scaling_rule_name)
        
        return True
    except KeyError:
        global _skip_sync
        if _skip_sync is True:
            print "WARNING '{}': Scaling rule does not exist, try running the script without --skip-sync flag".format(scaling_rule_name)
        else:
            print "WARNING '{}': Scaling rule does not exist in aliyun, have you created the scaling rule in aliyun?".format(scaling_rule_name)
        return False
    except ClientException:
        print "ERROR '{}': API connection issue, please try again".format(scaling_rule_name)
        print sys.exc_value
        print ""
        return False
    except:
        print "ERROR '{}': {}".format(scaling_rule_name, sys.exc_info)
        return False

def dump_current_rules(rules, cache_path):
    """ Save _current_rules into cache file """
    try:
        __location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
        with open(os.path.join(__location__, cache_path), "w") as file:
            yaml.dump(rules, file, default_flow_style=False)
    except:
        print "Error dumping current rules into cached_rules.yaml", sys.exc_value

def determine_scaling_group(rule_name):
    """ Detect scaling group name of a scaling rule """
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
    """ Ask a yes/no question """
    if _noconfirm:
        return True

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
    global _current_rules

    init(args)

    # Start modifying rules
    print "\nModifying scaling rules:"
    processed_mode_rules = {}   # Keep track of rules we want to processed (False means not yet processed)
    for a in _config:
        if a.find("default-") == -1:
            if _limit and a in _limit:  # If --limit is used, only process the ones in limit
                processed_mode_rules[a] = False
            elif not _limit:            # Process all loaded rules otherwise
                processed_mode_rules[a] = False                

    if _limit:
        for a in _limit:
            processed_mode_rules[a] = modify_scaling_rule(a)
    else:
        for a in _current_rules:
            processed_mode_rules[a] = modify_scaling_rule(a)
    
    # Process rules that wasn't found in aliyun, but are listed in mode config file
    added_one_or_more_rules = False
    print "\nThese rules are not found in aliyun:"
    for a in processed_mode_rules:
        if not processed_mode_rules[a]:
            rule_scaling_group = determine_scaling_group(a)
            if rule_scaling_group != None:
                print "{}: Should belong to ScalingGroup={}".format(a, rule_scaling_group)
                if rule_scaling_group not in _scaling_groups:
                    print "WARNING '{}': Scaling group doesn't exists".format(rule_scaling_group)
                else:
                    add_new_rule = query_yes_no("Do you want to create {} rule and attach to {} scaling group in aliyun?".format(a, rule_scaling_group))
                    if add_new_rule:
                        if create_and_attach_scaling_rule(a, rule_scaling_group):
                            processed_mode_rules[a] = True
                            _event_trigger_tasks[a]["bypass_skip"] = True
                            added_one_or_more_rules = True
            else:
                print "{}: Please check the naming convention (appname-upscale/appname-downscale)".format(a)

    if added_one_or_more_rules:
        print "Reloading current rules from aliyun"
        _current_rules = reconstruct_current_rules_cache()

    found_event_trigger_tasks = {}      # Tasks that exist in aliyun
    not_found_event_trigger_tasks = {}  # Tasks that aren't found in aliyun
    
    # Flag all loaded event-trigger task as not having valid name
    for a in _event_trigger_tasks:
        _event_trigger_tasks[a]["valid_name"] = False
    
    # For every scaling rule that found its pair of event-trigger task, flag that task as valid,
    # other event-trigger tasks will remain flagged as invalid otherwise and user will be asked if
    # they want to delete them at the end
    for a in processed_mode_rules:
        if processed_mode_rules[a]:
            if a in _event_trigger_tasks:   # If the rule exists in aliyun
                found_event_trigger_tasks[a] = _event_trigger_tasks[a] # Will modify them
                _event_trigger_tasks[a]["valid_name"] = True
            else:
                not_found_event_trigger_tasks[a] = a    

    print "\nProcessing found event triggered task in aliyun:"
    for a in found_event_trigger_tasks:
        create_event_trigger_task(a)

    print "\nList of event-trigger tasks in aliyun that are useless (no scaling rule attached to it) or not following our naming convention:"
    for a in _event_trigger_tasks:
        if not _event_trigger_tasks[a]["valid_name"]:
            print "INVALID '{}': Event trigger task in aliyun, you can choose to delete it at the end of this script".format(a)

    print "\nThese event-trigger task are not found in aliyun:"
    for a in not_found_event_trigger_tasks:
        print a
        cont = query_yes_no("Create new one? (consult with above list, maybe it exists under INVALID)")
        if not cont:
            continue
        create_event_trigger_task(a)

    print "\nYou can delete those event-trigger tasks that are useless (no scaling rule attached to it) or not following our naming convention here:"
    for a in _event_trigger_tasks:
        if not _event_trigger_tasks[a]["valid_name"]:
            cont = query_yes_no("INVALID '{}': Delete it?".format(a))
            if not cont:
                continue
            delete_event_trigger_task(a)

    # Dump modified _current_rules into cached_rules.yaml
    print "\nCaching all changed rules into cached_rules.yaml"
    reconstruct_current_rules_cache()

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
    
    # Optional noconfirm counter
    parser.add_argument(
        "-n",
        "--noconfirm",
        dest="noconfirm",
        action="store_true",
        help="Skip interactive prompts (yes to all)")

    # Specify output of "--version"
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s (version {version})".format(version=__version__))

    args = parser.parse_args()
    main(args)