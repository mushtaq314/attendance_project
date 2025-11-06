from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from attendance.models import Employee

class Command(BaseCommand):
    help = "Mark employees offline if not updated recently"

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(minutes=5)
        offline_count = Employee.objects.filter(
            last_location_ts__lt=cutoff, is_online=True
        ).update(is_online=False)
        self.stdout.write(self.style.SUCCESS(f"Marked {offline_count} employees offline."))
