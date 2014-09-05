from optparse import make_option
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):

    help = 'Makes Auto-Api Javascript representtaions of your Daabase schema.  Takes no options.  Configured in settings.py'

    def handle(self, **options):
        from google.appengine.ext import testbed
        testbed = testbed.Testbed()
        testbed.activate()
        testbed.init_all_stubs()
        from auto_api import js
        js.model_js()