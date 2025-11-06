from django.contrib import admin, messages
from django import forms
from django.utils.html import format_html
from django.db.models import Q
from datetime import datetime
from .models import Employee, AttendanceLog


class EmployeeAdminForm(forms.ModelForm):
    pin_input = forms.CharField(
        max_length=6,
        required=False,
        help_text="Enter new PIN (blank = auto-generate)"
    )

    class Meta:
        model = Employee
        fields = ['name', 'emp_code', 'pin_input']


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    form = EmployeeAdminForm
    list_display = ('name', 'emp_code', 'is_online', 'last_seen', 'location_display')

    def last_seen(self, obj):
        return obj.last_location_ts.strftime('%Y-%m-%d %H:%M:%S') if obj.last_location_ts else "Never"
    last_seen.short_description = "Last Seen"

    def location_display(self, obj):
        if obj.last_lat and obj.last_lng:
            return f"{obj.last_lat:.4f}, {obj.last_lng:.4f}"
        return "N/A"
    location_display.short_description = "Last Location"

    def save_model(self, request, obj, form, change):
        raw_pin = form.cleaned_data.get('pin_input')
        generated_pin = obj.set_pin(raw_pin)
        super().save_model(request, obj, form, change)
        msg = f"✅ PIN set manually for {obj.name}: {raw_pin}" if raw_pin else f"🎯 Auto-generated PIN: {generated_pin}"
        messages.success(request, msg)


# ==============================
# Custom Filter Form for Logs
# ==============================
class LogFilterForm(forms.Form):
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.all(),
        required=False,
        label="Filter by Employee"
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="From Date"
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="To Date"
    )


@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = ('employee', 'action', 'ts', 'latitude', 'longitude', 'show_map')
    readonly_fields = ('latitude', 'longitude', 'show_map')
    list_filter = ('action',)
    search_fields = ('employee__name', 'employee__emp_code')
    date_hierarchy = 'ts'
    change_list_template = 'attendance/logs_table.html'  # Custom template for filters

    def get_changelist(self, request, **kwargs):
        return super().get_changelist(request, **kwargs)

    def changelist_view(self, request, extra_context=None):
        """Inject custom filter form."""
        form = LogFilterForm(request.GET or None)
        qs = self.get_queryset(request)

        # Apply filters
        if form.is_valid():
            emp = form.cleaned_data.get('employee')
            start = form.cleaned_data.get('start_date')
            end = form.cleaned_data.get('end_date')

            if emp:
                qs = qs.filter(employee=emp)
            if start:
                qs = qs.filter(ts__date__gte=start)
            if end:
                qs = qs.filter(ts__date__lte=end)

        extra_context = extra_context or {}
        extra_context['form'] = form
        extra_context['cl'] = self.get_changelist_instance(request)
        extra_context['results'] = qs

        return super().changelist_view(request, extra_context=extra_context)

    def show_map(self, obj):
        """Show embedded Google Map for each log location."""
        if obj.latitude and obj.longitude:
            return format_html(
                '<iframe width="250" height="200" '
                'src="https://maps.google.com/maps?q={},{}&z=15&output=embed"></iframe>',
                obj.latitude, obj.longitude
            )
        return "📍 No location data"
    show_map.short_description = "Employee Location"
