# Celery CloudWatch

This is a simple monitoring tool that intercepts the results of Celery tasks and uploads the result to AWS CloudWatch.

## Configuration
Configuration is done through environment variables. The following environment variables must be set in order for `celery-cloudwatch` to work:

* `REDIS_URL`
* `AWS_CLOUDWATCH_ACCESS_KEY`
* `AWS_CLOUDWATCH_SECRET_KEY`
* `AWS_CLOUDWATCH_GROUP_NAME`

Optionally, the following environment variables may be set:

* `AWS_CLOUDWATCH_REGION`

The CloudWatch log group does not have to exist. If it doesn't exists, it will be created.

## Running

    celery cloudwatch

This requires you to have ran `setup.py` or installed this package through pip. Alternatively, run:

    python -m celery_cloudwatch
