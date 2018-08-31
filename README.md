# Autoscale Rules Mode
Script to automate the setting of autoscale config in aliyun, based on config files

## Workflow

- Scan all existing Scaling Rules, Scaling Groups, and Event-trigger Tasks.
- Compare all Scaling Rules with selected config files (default is `./config/normal/*.yaml`)
- Will only change the rules if they differ, or create new ones if they don't exist in aliyun (corresponding scaling groups must exist though)
- Compare all Event-trigger Tasks with selected config files, skip if there are no difference
- Will make sure that every scaling rule has their Event-trigger Tasks with correct configurations
- Will ask if user wants to delete invalid Event-trigger Tasks

Few things to note:
- The script assumes that all rules follow our naming convention, `app-name-upscale` and `app-name-downscale`
- Unlisted rule in the selected `yaml` file will use the `default-autoscale`/`default-downscale` values instead

## Usage
```
$ python2 autoscale-rules-mode.py -h
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
```

## Dependencies
Using python `2.7.15`
- `pyyaml`
- `aliyun-python-sdk-core`
- `aliyun-python-sdk-ess`

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

These event-trigger task are not found in aliyun:

You can delete those event-trigger tasks that are useless (no scaling rule attached to it) or not following our naming convention here:
INVALID 'go-testapp-upscale': Delete it? [Y/n] 
CHANGED 'go-testapp-upscale': Deleted event trigger task

Caching all changed rules into cached_rules.yaml
```
