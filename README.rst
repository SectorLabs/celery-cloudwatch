.. image:: https://scrutinizer-ci.com/g/SectorLabs/celery-cloudwatch/badges/build.png?b=master&s=dbee8972701eec8cb3f256360b6c8f2880a8eae7
    :target: https://scrutinizer-ci.com/g/SectorLabs/celery-cloudwatch/

.. image:: https://scrutinizer-ci.com/g/SectorLabs/celery-cloudwatch/badges/quality-score.png?b=master&s=b715993dcceb3ec81785e324f3cb36b17c40fa0f
    :target: https://scrutinizer-ci.com/g/SectorLabs/celery-cloudwatch/

.. image:: https://img.shields.io/badge/license-MIT-blue.svg

This is a simple monitoring tool that intercepts the results of Celery tasks and uploads the result to AWS CloudWatch.

Configuration
-------------
Configuration is done through environment variables. The following environment variables must be set in order for ``celery-cloudwatch`` to work:

* ``AWS_CLOUDWATCH_ACCESS_KEY``
* ``AWS_CLOUDWATCH_SECRET_KEY``
* ``AWS_CLOUDWATCH_GROUP_NAME``

Optionally, the following environment variables may be set:

* ``REDIS_URL="redis://"``
* ``AWS_CLOUDWATCH_REGION="eu-west-1"``

The CloudWatch log group does not have to exist. If it doesn't exists, it will be created.

Running
-------

.. code-block:: bash

    $ celery cloudwatch

This requires you to have ran ``setup.py`` or installed this package through pip. Alternatively, run:

.. code-block:: bash

    $ python -m celery_cloudwatch

Known issues
------------

* ``--broker`` on ``celery cloudwatch`` is ignored.
* No descriptive way to specify other brokers than Redis.

All brokers supported by Celery will work, simply specify the broker URL through the ``REDIS_URL`` environment variable.
