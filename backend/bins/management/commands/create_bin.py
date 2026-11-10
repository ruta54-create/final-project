"""python manage.py create_bin "Library Bin" --location "Library entrance"

Registers a new physical bin and prints the API key to put in the ESP32 code.
"""

from django.core.management.base import BaseCommand

from bins.models import Bin


class Command(BaseCommand):
    help = "Register a new smart bin and print its device API key"

    def add_arguments(self, parser):
        parser.add_argument("name")
        parser.add_argument("--location", default="")

    def handle(self, *args, **opts):
        bin = Bin.objects.create(name=opts["name"], location=opts["location"])
        self.stdout.write(self.style.SUCCESS(f"Bin #{bin.id} '{bin.name}' created."))
        self.stdout.write(f"API key (copy into both ESP32 sketches): {bin.api_key}")
