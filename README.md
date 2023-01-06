# nagios-check-amqp
A script to communicate with AMQP services, and outputs a roundtrip time usage. Compatible with Icinga2 graphite integration, but is not a dependency.

Compatible with multiple RabbitMQ servers. Very much an early stage of development, but primary focus has been completed.

Tested for RabbitMQ, ubuntu 22.04 and Icinga2

## Requirements
* python3
* pip
* [pika library](https://pypi.org/project/pika/)

## Setup
Place the check_amqp.py in the plugins folder for nagios/icinga2.

Place the amqp_credentials.yml in a folder. Default place is the same as the script itself.

In amqp_credentials.yml, make sure to have all the credentials correctly placed in the instance desired.

In Icinga2, make sure to have a variable to parse the desired rabbitmq instance.
