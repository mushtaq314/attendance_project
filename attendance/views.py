from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib import messages
from .models import Employee, AttendanceLog
from django.db.models import Q
import pandas as pd
import io
from datetime import datetime, date, timedelta
from django.views.decorators.csrf import csrf_exempt
import json


# Simple admin password (demo)
ADMIN_PASSWORD = "xdbs@2025!"

# --- SESSION KEYS ---
SESSION_EMP_KEY = "employee_id"

# ===========================
# EMPLOYEE VIEWS
# ===========================

def employee_view(request):
    """Public page where an employee selects their name and clicks buttons."""
    employees = Employee.objects.all().order_by('name')
    return render(request, 'attendance/employee.html', {'employees': employees})


@csrf_exempt
def api_action(request):
    """Employee action + location update"""
    if request.method == 'POST':
        data = json.loads(request.body)
        action = data.get('action')
        latitude = data.get('latitude')
        longitude = data.get('longitude')

        emp_id = request.session.get(SESSION_EMP_KEY)
        if not emp_id:
            return JsonResponse({'ok': False, 'error': 'not logged in'})

        try:
            emp = Employee.objects.get(id=emp_id)
        except Employee.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'employee not found'})

        # ✅ Save attendance log
        AttendanceLog.objects.create(
            employee=emp,
            action=action,
            latitude=latitude,
            longitude=longitude,
        )

        # ✅ Update employee live location and status
        emp.last_lat = latitude
        emp.last_lng = longitude
        emp.last_location_ts = timezone.now()
        emp.is_online = True
        emp.save(update_fields=['last_lat', 'last_lng', 'last_location_ts', 'is_online'])

        return JsonResponse({
            'ok': True,
            'action': action,
            'ts': timezone.now().isoformat()
        })

    return JsonResponse({'ok': False, 'error': 'invalid request'})
def employee_login_view(request):
    """Employee login using emp_code + PIN."""
    error = None
    if request.method == 'POST':
        emp_code = request.POST.get('emp_code', '').strip()
        pin = request.POST.get('pin', '').strip()
        try:
            emp = Employee.objects.get(emp_code=emp_code)
            if emp.check_pin(pin):
                request.session[SESSION_EMP_KEY] = emp.id
                request.session.set_expiry(20 * 60)
                return redirect('attendance:employee_dashboard')
            else:
                error = "Invalid PIN"
        except Employee.DoesNotExist:
            error = "Employee not found"
    return render(request, 'attendance/employee_login.html', {'error': error})


def employee_logout_view(request):
    request.session.pop(SESSION_EMP_KEY, None)
    return redirect('attendance:employee_login')


def employee_dashboard(request):
    """Employee dashboard after login."""
    emp_id = request.session.get(SESSION_EMP_KEY)
    if not emp_id:
        return redirect('attendance:employee_login')
    emp = get_object_or_404(Employee, pk=emp_id)
    return render(request, 'attendance/employee.html', {'employee': emp})


# ===========================
# ADMIN VIEWS
# ===========================

def admin_login(request):
    """Simple admin login using hardcoded password."""
    if request.method == 'POST':
        pwd = request.POST.get('password')
        if pwd == ADMIN_PASSWORD:
            request.session['is_admin'] = True
            return redirect('attendance:admin_panel')
        else:
            return render(request, 'attendance/admin_login.html', {'error': 'Invalid password'})
    return render(request, 'attendance/admin_login.html')


def admin_logout(request):
    request.session.pop('is_admin', None)
    return redirect('attendance:admin_login')


def admin_panel(request):
    """Admin dashboard showing employees and logs."""
    if not request.session.get('is_admin'):
        return redirect('attendance:admin_login')
    employees = Employee.objects.all().order_by('id')
    logs = AttendanceLog.objects.select_related('employee').order_by('-ts')[:200]
    return render(request, 'attendance/admin_panel.html', {'employees': employees, 'logs': logs})


@require_POST
def add_employee(request):
    if not request.session.get('is_admin'):
        return HttpResponseForbidden()
    name = request.POST.get('name')
    emp_code = request.POST.get('emp_code')
    if name and emp_code:
        emp, created = Employee.objects.get_or_create(emp_code=emp_code, defaults={'name': name})
        if created:
            # Generate PIN automatically for new employee
            new_pin = emp.set_pin()
            messages.success(request, f"Employee added successfully! PIN: {new_pin}")
        else:
            messages.warning(request, "Employee already exists.")
    return redirect('attendance:admin_panel')


@require_POST
def delete_employee(request, emp_id):
    if not request.session.get('is_admin'):
        return HttpResponseForbidden()
    emp = get_object_or_404(Employee, pk=emp_id)
    emp.delete()
    messages.success(request, f"Deleted employee {emp.name}")
    return redirect('attendance:admin_panel')


# ===========================
# NEW FEATURE — PIN MANAGEMENT
# ===========================

@require_POST
def set_employee_pin(request, emp_id):
    """Admin can manually set or regenerate an employee PIN."""
    if not request.session.get('is_admin'):
        return HttpResponseForbidden()
    emp = get_object_or_404(Employee, pk=emp_id)
    manual_pin = request.POST.get('manual_pin', '').strip()

    if manual_pin:
        if manual_pin.isdigit() and len(manual_pin) == 4:
            emp.set_pin(manual_pin)
            messages.success(request, f"PIN for {emp.name} updated manually: {manual_pin}")
        else:
            messages.error(request, "PIN must be a 4-digit number.")
    else:
        new_pin = emp.set_pin()  # auto-generate
        messages.success(request, f"New PIN generated for {emp.name}: {new_pin}")

    return redirect('attendance:admin_panel')


# ===========================
# ADMIN LOG MANAGEMENT
# ===========================

def admin_logs_json(request):
    if not request.session.get('is_admin'):
        return HttpResponseForbidden()
    logs = AttendanceLog.objects.select_related('employee').order_by('-ts')[:1000]
    data = [{
        'id': l.id,
        'employee_id': l.employee.id,
        'emp_code': l.employee.emp_code,
        'name': l.employee.name,
        'action': l.action,
        'ts': l.ts.isoformat()
    } for l in logs]
    return JsonResponse(data, safe=False)


@require_POST
def edit_log(request, log_id):
    if not request.session.get('is_admin'):
        return HttpResponseForbidden()
    log = get_object_or_404(AttendanceLog, pk=log_id)
    action = request.POST.get('action')
    ts_str = request.POST.get('ts')
    if action in ('login', 'logout', 'break_start', 'break_end'):
        log.action = action
    try:
        if ts_str:
            log.ts = datetime.fromisoformat(ts_str)
    except Exception:
        pass
    log.save()
    messages.success(request, "Log updated successfully!")
    return redirect('attendance:admin_panel')


# ===========================
# EXCEL EXPORT
# ===========================

def export_excel(request):
    """Admin-only Excel export of logs."""
    if not request.session.get('is_admin'):
        return HttpResponseForbidden()

    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    today = date.today()
    start_d = date.fromisoformat(start_str) if start_str else today
    end_d = date.fromisoformat(end_str) if end_str else today

    start_dt = datetime.combine(start_d, datetime.min.time())
    end_dt = datetime.combine(end_d, datetime.max.time())

    logs_qs = AttendanceLog.objects.select_related('employee') \
        .filter(ts__range=(start_dt, end_dt)) \
        .order_by('employee__name', 'ts')

    raw_rows = []
    for l in logs_qs:
        ts_naive = timezone.make_naive(l.ts)
        raw_rows.append({
            'log_id': l.id,
            'employee_id': l.employee.id,
            'emp_code': l.employee.emp_code,
            'name': l.employee.name,
            'action': l.action,
            'timestamp': ts_naive,
        })

    df_raw = pd.DataFrame(raw_rows)

    summary_rows = []
    if not df_raw.empty:
        df_raw['date'] = pd.to_datetime(df_raw['timestamp']).dt.date
        grouped = df_raw.groupby(['employee_id', 'name', 'emp_code', 'date'])
        for (emp_id, name, emp_code, day), g in grouped:
            actions = g.sort_values('timestamp')
            login_times = actions[actions['action'] == 'login']['timestamp'].tolist()
            logout_times = actions[actions['action'] == 'logout']['timestamp'].tolist()
            first_login = pd.to_datetime(login_times[0]) if login_times else pd.NaT
            last_logout = pd.to_datetime(logout_times[-1]) if logout_times else pd.NaT

            breaks = actions[actions['action'].isin(['break_start', 'break_end'])][['action', 'timestamp']].values.tolist()
            total_break_secs = 0
            stack = []
            for act, ts in breaks:
                ts_dt = pd.to_datetime(ts)
                if act == 'break_start':
                    stack.append(ts_dt)
                elif act == 'break_end' and stack:
                    total_break_secs += (ts_dt - stack.pop()).total_seconds()

            total_work_secs = None
            if pd.notna(first_login) and pd.notna(last_logout):
                total_work_secs = (last_logout - first_login).total_seconds() - total_break_secs

            summary_rows.append({
                'employee_id': emp_id,
                'emp_code': emp_code,
                'name': name,
                'date': day.isoformat(),
                'first_login': first_login.replace(tzinfo=None).isoformat() if pd.notna(first_login) else '',
                'last_logout': last_logout.replace(tzinfo=None).isoformat() if pd.notna(last_logout) else '',
                'total_break_minutes': round(total_break_secs / 60, 2),
                'work_hours': round(total_work_secs / 3600, 2) if total_work_secs is not None else ''
            })

    df_summary = pd.DataFrame(summary_rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        (df_summary if not df_summary.empty else pd.DataFrame(columns=['No Data'])).to_excel(writer, sheet_name='Summary', index=False)
        (df_raw if not df_raw.empty else pd.DataFrame(columns=['No Data'])).to_excel(writer, sheet_name='RawLogs', index=False)

    output.seek(0)
    filename = f"attendance_{start_d.isoformat()}_to_{end_d.isoformat()}.xlsx"
    response = HttpResponse(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def api_all_locations(request):
    employees = Employee.objects.exclude(last_lat__isnull=True)
    data = [{
        'name': e.name,
        'last_lat': e.last_lat,
        'last_lng': e.last_lng,
        'last_seen': e.last_location_ts.strftime('%Y-%m-%d %H:%M:%S') if e.last_location_ts else '',
        'is_online': e.is_online,
    } for e in employees]
    return JsonResponse(data, safe=False)

def filter_logs(request):
    emp_id = request.GET.get('employee')
    start = request.GET.get('start')
    end = request.GET.get('end')

    logs = AttendanceLog.objects.all().order_by('-ts')

    if emp_id:
        logs = logs.filter(employee_id=emp_id)
    if start:
        logs = logs.filter(ts__date__gte=start)
    if end:
        logs = logs.filter(ts__date__lte=end)

    return render(request, 'attendance/logs_table.html', {'logs': logs})