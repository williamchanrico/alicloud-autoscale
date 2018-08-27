# Autoscale Rules Mode
Script to automate the setting of autoscale rules in aliyun, based on config file

## Usage
```
$ python2 autoscale-rules-mode.py -h
usage: autoscale-rules-mode.py [-h] [-m MODE] [-l LIMIT] [-s] [-v] [--version]
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
```

## Example

- The script will skip rules that hasn't been changed
- The script assumes all rules follow our naming convention, `app-name-upscale` and `app-name-downscale`
- Unlisted rule in selected `yaml` file will use the `default-autoscale`/`default-downscale` instead
- Rules that are listed in `yaml` file but are not found in aliyun, can be added automatically depends on user's choice

```
$ python2 autoscale-rules-mode.py --mode normal your_access_key your_secret_key region
Initializing API client object using the configured access key
Loading scaling groups information from aliyun
Loading selected mode config from config/normal.yaml
Loading current rules from aliyun (cached_rules.yaml is ignored)
There are total of 140 scaling rules detected

SKIPPED 'go-cartapp-upscale': No difference between the current and the new rule
SKIPPED 'go-wallet-upscale': No difference between the current and the new rule
CHANGED 'node-frontend-discovery-home-downscale': Successfully modified the scaling rule
SKIPPED 'go-mojito-wishlist-upscale': No difference between the current and the new rule
SKIPPED 'go-notifier-upscale': No difference between the current and the new rule
.
.
.
SKIPPED 'go-campaign-tx-deduct-upscale': No difference between the current and the new rule
CHANGED 'go-mojito-wishlist-downscale': Successfully modified the scaling rule
SKIPPED 'node-frontend-discovery-misc-upscale': No difference between the current and the new rule
CHANGED 'pgbouncer-merchant-downscale': Successfully modified the scaling rule
CHANGED 'go-feeds-downscale': Successfully modified the scaling rule

These rules are not found in aliyun:
go-test-unadded-upscale: should belong to ScalingGroup=go-test-unadded
go-testapp-upsca: can't determine its ScalingGroup, please check the naming convention (appname-upscale/appname-downscale)
go-testapp-upscale: should belong to ScalingGroup=go-testapp

Do you want to create those rules in aliyun? [Y/n] y
WARNING 'go-test-unadded': Scaling group doesn't exists
CHANGED 'go-testapp-upscale': Created scaling rule and attached it to scaling group 'go-testapp'

Caching all changed rules into cached_rules.yaml
```
