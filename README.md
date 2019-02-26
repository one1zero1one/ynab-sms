# Intro

Do you use YNAB with mutliple people? use `ynab-sms.py` to notify other users of your budget (or/and to a slack channel) to keep everyone in the loop! The script uses flag colors to identify who's transaction it is. For instance, I mark my transactions with a blue flag, and my wife marks hers with a purple flag. The script will also alert all users if a category's budgeted amount gets changed.

## Getting started

## Install Requirements

The script requires python 3. Install the required python packages with `pip install -r requirements.txt`

## Configure

Copy `settings.json.example` to `settings.json` and then modify with your settings. You'll need a Personal Access Token from your [YNAB Developer Settings](https://app.youneedabudget.com/settings/developer),a [Twilio](https://www.twilio.com/sms) Programmable SMS account for getting notified via sms and/or a [Slack](https://api.slack.com/custom-integrations/legacy-tokens) (legacy) Token for getting notification on a slack channel.

### Sample Config

The configuration is broken up into six sections.

In the `notify` section you need to select the notification methods. In below example, both methods are enabled.

```json
 "notify": ["slack", "twilio"]
```

In the `frequency` section you need to set how often the script will run (in _minutes_). Keep in mind the YNAB API call limits, which are currently 200 calls per hour, and the script makes three calls per run. Default config is once every 10 minutes (18 calls).

```json
 "frequency": 10
```

In the `currency` section, setup your desired coin sign.

```json
"coin": "EUR"
```

In the `ynab` section you'll need to fill in your budget ID, which can be found in the url bar when you're editing your budget: `https://app.youneedabudget.com/THIS IS YOUR BUDGET ID/budget`, as well as a Personal Access Token from your YNAB Developer Settings.

(The information below is all random)

```json
    "ynab": {
        "budget": "h1347489-2b23-6dcf-feb9-6204ba34a4fe",
        "token": "44b913a04a2f3c898d498a22b34a236205664ba97d68585446dcff6c04feb6"
    },
```

In the `twilio` section you'll need your Account SID, auth token, and your programmable sms number.

```json
    "twilio": {
        "sid": "ee5a1a322e6415d68cAC4fef0bf61899ed",
        "token": "5eb13d609b7edf2fd7b4c48ceef81923",
        "number": "+12135552560"
    },
```

In the `slack` section, you'll need your API token, and the chanel you want to send the notifications to.

```json
 "slack:": {
        "token": "xoxp-xxx-yyy-zzz-aaa",
        "channel": "#finance"
    }
```

Finally, in the `users` section add each person you want to get SMS alerts, and the flag color for the transactions they enter. Transactions with no or unknown flags (not defined here) will not be sent by SMS but will be sent to slack.

```json
    "users": [
        {
            "name": "Alice",
            "number": "+16615557189",
            "flag": "purple"
        },
        {
            "name": "Bob",
            "number": "+13235557167",
            "flag": "blue"
        }
    ]
}
```

## Run as a script

Once configured, run `python3 ynab-sms.py`. It will automatically run the job. The script writes a couple json files to the local directory to keep track of past data, so make sure it has write permissions. The script will notify only about _new_ transactions.

## Run in docker

Build with `docker build --tag ynab-sms .` and run with `docker run -d --restart unless-stopped ynab-sms:latest`.

## Improvements

Currently this script grabs all possible transactions. A future version should use the delta api instead. The payee list should be cached as well.

## Credits

Kudos to [ljb2of3](https://github.com/ljb2of3) for doing all the heavy lifting (calculation of things and main logic), I have forked and butchered the code to fit my needs.