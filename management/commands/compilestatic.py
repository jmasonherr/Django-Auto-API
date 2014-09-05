import re
from sweatguru import settings
from subprocess import Popen, PIPE
from optparse import make_option
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):

    help = 'Compiles handlebars and javascript into one.  Takes no options.  Configured in settings.py'

    def handle(self, **options):
        import predeploy