from celery.bin.base import Command

from .monitor import main as monitor


class CloudWatchCommand(Command):
    """Monitors the execution of Celery tasks
    and uploads the results of succeeded and
    failed tasks to AWS CloudWatch."""

    def add_arguments(self, parser):
        """Allows us to expose additional command
        line options.

        Arguments:
            parser:
                The :see:argparse parser to add
                the command line options to.
        """

    def run(self, **_):
        """Invoked when the user runs `celery cloudwatch`."""

        monitor()
