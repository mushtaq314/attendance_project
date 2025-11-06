# attendance/urls.py
from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.employee_login_view, name='employee_login'),  # first page = login
    path('employee/', views.employee_view, name='employee_view'),
    path('employee-dashboard/', views.employee_dashboard, name='employee_dashboard'),
    path('api/action/', views.api_action, name='api_action'),
    path('set-pin/<int:emp_id>/', views.set_employee_pin, name='set_employee_pin'),

    # Admin area
    path('admin-login/', views.admin_login, name='admin_login'),
    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('admin/logout/', views.admin_logout, name='admin_logout'),
    path('admin/add-employee/', views.add_employee, name='add_employee'),
    path('admin/delete-employee/<int:emp_id>/', views.delete_employee, name='delete_employee'),
    path('admin/logs/', views.admin_logs_json, name='admin_logs_json'),
    path('export/', views.export_excel, name='export_excel'),
    path('admin/edit-log/<int:log_id>/', views.edit_log, name='edit_log'),
    path('filter-logs/', views.filter_logs, name='filter_logs'),

    # Employee logout
    path('employee-logout/', views.employee_logout_view, name='employee_logout'),
]
