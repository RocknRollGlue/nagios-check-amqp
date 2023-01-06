#!/usr/bin/env python3
import pika, pika.exceptions
import argparse
import time
import yaml
import sys
import multiprocessing
parser = argparse.ArgumentParser()
parser.add_argument('-f', '--file', help='Filepath of credentials yml file.', default="amqp_credentials.yml")
parser.add_argument('-i', '--instance', help="name of instance in the credentials yml file", default="rabbitmq_dev")

parser.add_argument('-e', '--exchange', help='Name of the exchange required. Defaults to RabbitMQ default exchange', default='')
parser.add_argument('-v', '--virtualhost', help='Virtual host', default='')
parser.add_argument('-q', '--queue', help='Name of queue', required=True)
parser.add_argument('-r', '--replyto', help='Channel for the consumer to send reply to', required=True)

parser.add_argument('-b', '--body', help='Body of the AMQP message', default='')
parser.add_argument('-H', '--headers', help='Header variables of the AMQP message in "key:value"', nargs='*', default={})

parser.add_argument('--response-header', help="Expected reply of the pinged consumer in k:v pairs. Default ping:pong", nargs='*', default='ping:pong')
parser.add_argument('--response-body', help='Expected reply of the pinged consumers body default empty string', default='')
parser.add_argument('-w', '--warning_level', help='Warning threshold in ms of roundtrip of AMQP request', default=5000)
parser.add_argument('-c', '--critical_level', help='Critical threshold in ms of roundtrip of AMQP request', default=20000)
params=parser.parse_args()

def prepareHeaderDict():
    dict = {}
    if params.headers is None:
        return dict

    for value in params.headers:
        dict[value.split(":")[0]] = value.split(":")[1]
    return dict

def getStatus(response_time, warning_level, critical_level):
    '''
    Gets status based on nagios standard.
    Returns a dictionary with the keys: code, string.
    Code indicates an exit code, nagios takes as 
    '''
    # we default to unknown state
    # Look at https://icinga.com/docs/icinga-2/latest/doc/05-service-monitoring/#status
    status_dict = {
        "code": 3,
        "string": "UNKOWN"
    }
    if response_time >= critical_level:
        status_dict = {
            "code": 2,
            "string": "CRITICAL"
        }
    elif response_time >= warning_level:
        status_dict = {
            "code": 1,
            "string": "WARNING"
        }
    elif response_time > 0 and response_time < warning_level:
        status_dict = {
            "code": 0,
            "string": "OK"
        }
    return status_dict

def sendAMQP(url,
        credentials_user,
        credentials_password,
        port,
        exchange,
        vhost,
        header,
        body,
        queue,
        reply_channel):
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                url, 
                credentials=pika.PlainCredentials(credentials_user, credentials_password),
                port=port, 
                virtual_host=vhost
            )
        )
        channel = connection.channel()
        
        
        channel.basic_publish(
            exchange=exchange,
            routing_key=queue,
            body=body,
            properties=pika.BasicProperties(
                headers=prepareHeaderDict(),
                reply_to=reply_channel
            ),
        )
        
        channel.close()
        return True
    except pika.exceptions.AMQPError:
        return False

def receiveFirstAMQPMessage(url,
        credentials_user,
        credentials_password,
        port,
        vhost,
        reply_channel):

    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=url, 
        credentials=pika.PlainCredentials(
            credentials_user, credentials_password
        ),
        port= port,
        virtual_host=vhost
    ))

    channel = connection.channel()
    channel.queue_declare(queue=reply_channel)
    def callback(ch, method, properties, body):
        channel.stop_consuming()

    channel.basic_consume(queue=reply_channel, on_message_callback=callback, auto_ack=True)
    channel.start_consuming()

def fetchCredentials(file, instance):
    try:
        with open(file, 'r') as stream:
            try:
                parsed_yaml=yaml.safe_load(stream)
                credentials= {
                    "url" : parsed_yaml[instance]["url"],
                    "port" : parsed_yaml[instance]["port"],
                    "username" : parsed_yaml[instance]["username"],
                    "password" : parsed_yaml[instance]["password"]
                }
                return credentials
            except:
                print("SERVICE UNKNOWN - Unable to read credentials from file")
                sys.exit(3)
    except FileNotFoundError as e:
        print("SERVICE UNKNOWN - Unable to find file: " + file)
        sys.exit(3)

def parseArguments():
    #Attempt to parse arguments
    try:
        params.warning_level = int(params.warning_level)
        params.critical_level = int(params.critical_level)
    except ValueError:
        print('SERVICE UNKNOWN: INCORRECT PARAMETERS PARSED')
        sys.exit(3)    

def prepareTest():
    parseArguments()
    credentials = fetchCredentials(params.file, params.instance)
    
    consumer = multiprocessing.Process(target=receiveFirstAMQPMessage, 
        args=(
            credentials['url'], 
            credentials['username'], 
            credentials['password'], 
            credentials['port'], 
            params.virtualhost, 
            params.replyto
        )
    )
    #receiveFirstAMQPMessage(credentials['url'], credentials['username'], credentials['password'], credentials['port'], params.virtualhost, params.replyto )
    t0 = time.time()
    consumer.start()
    publisherSuccess = sendAMQP(
        credentials['url'], 
        credentials['username'], 
        credentials['password'],
        credentials['port'],
        params.exchange,
        params.virtualhost,
        params.headers,
        params.body,
        params.queue,
        params.replyto
    )
    if not publisherSuccess:
        print("SERVICE UNKNOWN - Unable to send AMQP")
        sys.exit(3)

    # we divide by 1000 to get seconds instead of ms
    consumer.join(params.critical_level / 1000)
    # If service is still alive due to timeout, we want to terminate it. Otherwise it will go on for potentially forever in the background
    if consumer.is_alive():
        consumer.terminate()
    
    t1 = time.time()
    time_used = round((t1-t0)*1000,2)
    status_dict = getStatus(time_used, params.warning_level, params.critical_level)
    print("SERVICE {status}: Roundtrip {time}ms|'rta'={value};{warn_value};{crit_value};{min};{max}".format(
        status=status_dict['string'],
        time=time_used,
        value=time_used,
        warn_value=params.warning_level,
        crit_value=params.critical_level,
        min=0,
        max=params.critical_level,
    ))
    sys.exit(status_dict["code"])

prepareTest()
