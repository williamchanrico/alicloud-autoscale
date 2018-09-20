# Autoscale Rules Mode

Script to automate the setting of autoscale config in aliyun, based on config files

Default config dir is `./config/normal`, so just add `your-app-name.yaml` there if you're not sure.

Follow the example in `./config/normal/default.yaml`

## Workflow

- Scan all existing Scaling Rules, Scaling Groups, and Event-trigger Tasks.
- Compare all Scaling Rules with selected config files (default is `./config/normal/*.yaml`)
- Will only change the rules if they differ, or create new ones if they don't exist in aliyun (corresponding scaling groups must exist though)
- Check if MinInstance and MaxInstance is specified in each rules, for rules that have those values, make sure their scaling group in aliyun has the same min/max instance size
- Compare all Event-trigger Tasks with selected config files, skip if there are no difference
- Will make sure that every scaling rule has their Event-trigger Tasks with correct configurations
- Will ask if user wants to delete invalid Event-trigger Tasks

Few things to note:
- The script assumes that all rules follow our naming convention, `app-name-upscale` and `app-name-downscale`
- Unlisted rule in the selected `yaml` file will use the `default-autoscale`/`default-downscale` values instead

## Usage

```
$ python2 autoscale-rules-mode.py --help
usage: autoscale-rules-mode.py [-h] [-m MODE] [-l LIMIT] [-s] [-v] [-n]
                                [--version]  access_key_id access_key_secret region_id

positional arguments:
access_key_id                       Accesskey ID for aliyun account
access_key_secret                   AccessKey secret for aliyun account
region_id                           ID of the region where the service is called

optional arguments:
-h, --help                          Show this help message and exit
-m MODE, --mode MODE                Autoscale event-trigger task mode config
-l LIMIT, --limit LIMIT             Limit target rules
-o LOG_FILE, --log-file LOG_FILE    Absolute path for log file, default:
                                    'log/autoscale_rules_mode.log'
-s, --skip-sync                     Skip synching cached_rules.yaml for faster runtime if
                                    you're sure that no rules has been changed in aliyun
-v, --verbose                       Verbosity (-v, -vv, etc)
-n, --noconfirm                     Skip interactive prompts (yes to all)
--version                           Show program's version number and exit
```

## Dependencies

Using python `2.7.15`

`$ pip2 install -r requirements.txt`
- `aliyun-python-sdk-core==2.8.7`
- `aliyun-python-sdk-ess==2.2.5`
- `pycryptodome==3.6.6`
- `PyYAML==3.13`

## Example

```
$ python2 autoscale-rules-mode.py --mode normal your_access_key your_secret_key region
Initializing API client object using the configured access key
Loading selected mode config from config/normal/*.yaml
Loading scaling groups information from aliyun
Loading current rules from aliyun (cached_rules.yaml is ignored)
Loading event-trigger tasks information from aliyun
There are total of 136 scaling rules detected

Modifying scaling rules:
SKIPPED 'go-cartapp-upscale': No difference between the current and the new rule
SKIPPED 'go-wallet-upscale': No difference between the current and the new rule
SKIPPED 'node-frontend-discovery-home-downscale': No difference between the current and the new rule
SKIPPED 'go-mojito-wishlist-upscale': No difference between the current and the new rule
.
.
.
SKIPPED 'go-mojito-wishlist-downscale': No difference between the current and the new rule
SKIPPED 'node-frontend-discovery-misc-upscale': No difference between the current and the new rule
SKIPPED 'pgbouncer-merchant-downscale': No difference between the current and the new rule
SKIPPED 'go-feeds-downscale': No difference between the current and the new rule

These rules are not found in aliyun:
go-test-unadded-upscale: Should belong to ScalingGroup=go-test-unadded
WARNING 'go-test-unadded': Scaling group doesn't exists
go-testapp-downsdfadkf: Please check the naming convention (appname-upscale/appname-downscale)

Processing found event triggered task in aliyun:
SKIPPED 'go-cartapp-upscale': No difference between the current and the new event trigger task rule
SKIPPED 'go-wallet-upscale': No difference between the current and the new event trigger task rule
SKIPPED 'node-frontend-discovery-home-downscale': No difference between the current and the new event trigger task rule
SKIPPED 'go-mojito-wishlist-upscale': No difference between the current and the new event trigger task rule
SKIPPED 'go-notifier-upscale': No difference between the current and the new event trigger task rule
.
.
.
SKIPPED 'pgbouncer-merchant-downscale': No difference between the current and the new event trigger task rule
SKIPPED 'go-feeds-downscale': No difference between the current and the new event trigger task rule
SKIPPED 'go-orderapp-wscart-downscale': No difference between the current and the new event trigger task rule

List of event-trigger tasks in aliyun that are useless (no scaling rule attached to it) or not following our naming convention:
INVALID 'go-testapp-upscale': Event trigger task in aliyun, you can choose to delete it at the end of this script

You can delete those event-trigger tasks that are useless (no scaling rule attached to it) or not following our naming convention here:
INVALID 'go-testapp-upscale': Delete it? [Y/n]
CHANGED 'go-testapp-upscale': Deleted event trigger task

Caching all changed rules into cached_rules.yaml
```

## Debugging Log Example

```
[03/09/2018 04:17:55 PM] Modified Scaling Rule go-goldmerchant-upscale:
OLD => {'ScalingRuleAri': 'ari:acs:ess:ap-southeast-1:1208559439424161:scalingrule/asr-t4n3691dmt1t3xi5007b', 'ScalingGroupId': 'asg-t4nawf0lvwrygfltfnca', 'ScalingRuleId': 'asr-t4n3691dmt1t3xi5007b', 'AdjustmentValue': 65, 'ScalingRuleName': 'go-goldmerchant-upscale', 'Cooldown': 60, 'AdjustmentType': 'PercentChangeInCapacity'}

NEW => {'Threshold': 60.0, 'TriggerAfter': 3, 'ComparisonOperator': '>=', 'Cooldown': 60, 'AdjustmentType': 'PercentChangeInCapacity', 'MetricItem': 'CpuUtilization', 'RefreshCycleSeconds': 60, 'Condition': 'Average', 'AdjustmentValue': 65}

[06/09/2018 08:40:18 AM] Modified Scaling Group Size go-testapp:
OLD => MinInstance: 0, MaxInstance: 1

NEW => MinInstance: 0, MaxInstance: 3

[03/09/2018 04:17:57 PM] Created Event-trigger Task go-goldmerchant-upscale: {'Threshold': 60.0, 'TriggerAfter': 3, 'ComparisonOperator': '>=', 'Cooldown': 60, 'AdjustmentType': 'PercentChangeInCapacity', 'MetricItem': 'CpuUtilization', 'RefreshCycleSeconds': 60, 'Condition': 'Average', 'AdjustmentValue': 65}

[03/09/2018 04:17:58 PM] Disabled Event-trigger Task: asg-t4nawf0lvwrygfltfnca_8d480f9e-97ce-4b26-94f0-549e03a65c9a

[03/09/2018 04:17:59 PM] Deleted Event-trigger task: {'MetricItem': 'CpuUtilization', 'Statistics': 'Average', 'Name': 'go-goldmerchant-upscale', 'alarmActions': {'alarmAction': ['ari:acs:ess:ap-southeast-1:1208559439424161:scalingrule/asr-t4n3691dmt1t3xi5007b']}, 'TriggerAfter': 3, 'EvaluationCount': 3, 'Period': 60, 'MetricType': 'system', 'ComparisonOperator': '>=', 'State': 'OK', 'Enable': False, 'AlarmTaskId': 'asg-t4nawf0lvwrygfltfnca_38de7bd0-bac5-492b-91c0-fc1686252028', 'ScalingGroupId': 'asg-t4nawf0lvwrygfltfnca', 'valid_name': True, 'Threshold': 65.0, 'RefreshCycleSeconds': 60, 'MetricName': 'CpuUtilization', 'Condition': 'Average', 'Dimensions': {'Dimension': [{'DimensionValue': 'asg-t4nawf0lvwrygfltfnca', 'DimensionKey': 'scaling_group'}, {'DimensionValue': '1208559439424161', 'DimensionKey': 'userId'}]}}
```

## Version

```
$ python2 autoscale-rules-mode.py --version
autoscale-rules-mode.py (version 0.2.4)
```