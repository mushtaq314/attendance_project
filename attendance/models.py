from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
import random


class Employee(models.Model):
    emp_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    pin_hash = models.CharField(max_length=128, blank=True)

    # 🌍 New fields for tracking
    is_online = models.BooleanField(default=False)
    last_location_ts = models.DateTimeField(null=True, blank=True)
    last_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    last_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    def set_pin(self, raw_pin=None):
        """Set or generate a secure PIN for the employee."""
        if not raw_pin:
            raw_pin = str(random.randint(1000, 9999))
        self.pin_hash = make_password(raw_pin)
        self.save(update_fields=['pin_hash'])
        return raw_pin

    def check_pin(self, raw_pin):
        if not self.pin_hash:
            return False
        return check_password(raw_pin, self.pin_hash)

    def update_status(self, online: bool, lat=None, lng=None):
        """🔁 Update online/offline + location tracking"""
        self.is_online = online
        self.last_location_ts = timezone.now()
        if lat and lng:
            self.last_lat = lat
            self.last_lng = lng
        self.save(update_fields=['is_online', 'last_location_ts', 'last_lat', 'last_lng'])

    def __str__(self):
        return f"{self.name} ({self.emp_code})"


class AttendanceLog(models.Model):
    ACTION_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('break_start', 'Break Start'),
        ('break_end', 'Break End'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    ts = models.DateTimeField(auto_now_add=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_address = models.CharField(max_length=255, blank=True, null=True)

    def save(self, *args, **kwargs):
        """Auto-update employee status on each new log"""
        super().save(*args, **kwargs)

        # 🔄 Update employee last seen + online/offline
        if self.action == 'login':
            self.employee.update_status(True, self.latitude, self.longitude)
        elif self.action == 'logout':
            self.employee.update_status(False, self.latitude, self.longitude)
        else:
            # Breaks or others update only location timestamp
            self.employee.update_status(self.employee.is_online, self.latitude, self.longitude)

    def __str__(self):
        return f"{self.employee.emp_code} - {self.action} @ {self.ts.strftime('%Y-%m-%d %H:%M:%S')}"
