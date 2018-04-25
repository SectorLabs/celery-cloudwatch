from datetime import datetime
import json
import logging
import os
import sys

from botocore.exceptions import ClientError
from celery import Celery
import boto3
import psutil

LOGGER = logging.getLogger(__name__)

SEQUENCE_TOKENS = {}


def get_sequence_token(cloudwatch, log_group, log_stream):
    """Gets the next sequence token to use for uploading
    a log even to CloudWatch.

    Arguments:
        cloudwatch:
            The Boto3 CloudWatch client to use.

        log_group:
            The name of the log group to
            get the sequence token for.

        log_stream:
            The name of the log stream
            to get the sequence token for.

    Returns:
        The sequence token to use to upload the
        next log, or None if the log stream is empty.
    """

    token = SEQUENCE_TOKENS.get(log_stream)

    if not token:
        result = cloudwatch.describe_log_streams(
            logGroupName=log_group,
            logStreamNamePrefix=log_stream,
            limit=1
        )

        token = result['logStreams'][0].get('uploadSequenceToken')

    SEQUENCE_TOKENS[log_stream] = token
    return token


def get_timestamp_utc():
    """Gets the current date/time in UTC neutral
    timestamp, formatted as the amount of milliseconds
    that passed since January 1, 1970 (unix epoch).

    Returns:
        The current time as timestamp.
    """

    return int(datetime.utcnow().strftime('%s')) * 1000


def upload_log_event(cloudwatch, log_group, log_stream, data):
    """Uploads a log event to CloudWatch logs.

    Arguments:
        cloudwatch:
            The Boto3 CloudWatch client to
            use to upload the log event.

        log_group:
            The CloudWatch log group to upload
            the log event to.

        log_stream:
            The CloudWatch log stream to upload
            the log event to.

        data:
            The data to associate with
            the log event.

    """

    params = {
        'logGroupName': log_group,
        'logStreamName': log_stream,
        'logEvents': [{
            'timestamp': get_timestamp_utc(),
            'message': json.dumps(data)
        }],
    }

    token = get_sequence_token(
        cloudwatch,
        log_group,
        log_stream
    )

    if token:
        params['sequenceToken'] = token

    response = cloudwatch.put_log_events(**params)
    SEQUENCE_TOKENS[log_stream] = response['nextSequenceToken']


def _calculate_max_tasks():
    """Calculates the maximum amount of tasks we can keep in
    memory by taking the current amount of free memory into
    account.

    We assume an average of 1000 bytes per tasks, then
    compute how many tasks the currently free memory can
    hold, but only compute against 80% of the current
    free memory to make sure we never exceed it.

    Returns:
        The maximum amount of tasks we can keep in memory.
    """

    free_memory = (psutil.virtual_memory().free / 100) * 80
    max_tasks = free_memory / 1000

    LOGGER.info('Computed a maximum of %d tasks with %d bytes of free memory',
                max_tasks,
                free_memory)

    return max_tasks


def monitor(app, cloudwatch, streams):
    """Monitors the specified Celery app and uploads
    the results of tasks to CloudWatch.

    Arguments:
        app:
            The Celery app to monitor.

        cloudwatch:
            The Boto3 CloudWatch client to
            use to upload logs with.

        streams:
            Log streams configuration.
    """

    state = app.events.State(
        max_tasks_in_memory=_calculate_max_tasks()
    )

    def on_task_received(event):
        """Event handler for the 'task-received' event
        has been received.

        All we do here is update the internal state
        of the task the event is about.

        This is important because the 'task-received'
        event is the only event that inclues the name
        of the task. In order to retrieve a task's name
        for other events, we must have recorded the
        'task-received' event.
        """

        LOGGER.debug('Received \'%s\' - %s', event['type'], str(event))

        state.event(event)

    def on_task(log_group, log_stream):
        """Handler for whenever a event is received
        from Celery.

        Arguments:
            log_group:
                The name of the CloudWatch log group
                to upload the logs to.

            log_stream:
                The name of the CloudWatch log group
                to upload the logs to.
        """

        def proxy(event):
            LOGGER.debug('Received \'%s\' - %s', event['type'], str(event))

            state.event(event)
            task = state.tasks.get(event['uuid'])

            upload_log_event(
                cloudwatch,
                log_group,
                log_stream,
                {
                    'name': task.name,
                    'args': task.args,
                    'kwargs': task.kwargs,
                    'event': event
                }
            )

        return proxy

    with app.connection() as connection:
        # we must intercept the task-received event, but not
        # log about it because without it, we wouldn't be able
        # to retrieve the task name later
        handlers = {
            'task-received': on_task_received
        }

        # define handlers for all user-defined log streams
        for event_name, (log_group, log_stream) in streams.items():
            handlers[event_name] = on_task(log_group, log_stream)

        # start capturing events from celery
        recv = app.events.Receiver(connection, handlers=handlers)
        recv.capture(limit=None, timeout=None, wakeup=True)


def main():
    # set up logging, make sure to only show critical errors
    # from third-party packages
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('botocore').setLevel(logging.CRITICAL)
    logging.getLogger('kombu').setLevel(logging.CRITICAL)

    # acquire the the cloudwatch group name
    aws_log_group = os.environ.get('AWS_CLOUDWATCH_GROUP_NAME')

    # check for required environment variables
    if not aws_log_group:
        LOGGER.error('AWS_CLOUDWATCH_GROUP_NAME not set')
        sys.exit(1)

    # get the broker configuration
    broker_url = os.environ.get('REDIS_URL', 'redis://')

    # set up the celery application
    app = Celery(broker=broker_url)
    LOGGER.info('Connected to broker at %s', broker_url)

    # acquire the AWS configuration, if AWS_CLOUDWATCH_ACCESS_KEY
    # and/or AWS_CLOUDWATCH_SECRET_KEY are not set, Boto should
    # get these from the user's local environment
    aws_config = {
        'aws_access_key_id': os.environ.get(
            'AWS_CLOUDWATCH_ACCESS_KEY'
        ),
        'aws_secret_access_key': os.environ.get(
            'AWS_CLOUDWATCH_SECRET_KEY'
        ),
        'region_name': os.environ.get(
            'AWS_CLOUDWATCH_REGION',
            'eu-west-1'
        )
    }

    # define the streams to log about, the key is the
    # celery event to react to
    streams = {
        'task-failed': (aws_log_group, 'failure'),
        'task-succeeded': (aws_log_group, 'success'),
        'task-retried': (aws_log_group, 'retry'),
        'task-revoked': (aws_log_group, 'revoke'),
        'task-rejected': (aws_log_group, 'reject')
    }

    # set up the boto3/cloudwatch client
    ec2 = boto3.client('ec2', **aws_config)
    cloudwatch = boto3.client('logs', **aws_config)

    # make sure we're succesfully authenticated by making
    # a dumy call to describe_regions()
    ec2.describe_regions()

    # make sure the cloudwatch log group exists
    try:
        cloudwatch.create_log_group(logGroupName=aws_log_group)
        LOGGER.info('Created CloudWatch log group named "%s"', aws_log_group)
    except ClientError:
        LOGGER.info('CloudWatch log group named "%s" already exists', aws_log_group)

    # make sure the cloudwatch log streams exists
    for _, (_, aws_log_stream) in streams.items():
        try:
            cloudwatch.create_log_stream(
                logGroupName=aws_log_group, logStreamName=aws_log_stream)
            LOGGER.info('Created CloudWatch log stream named "%s"', aws_log_stream)
        except ClientError:
            LOGGER.info('CloudWatch log stream named "%s" already exists', aws_log_stream)

    # start monitoring
    monitor(app, cloudwatch, streams)


if __name__ == '__main__':
    main()
