from django.urls import path
from . import views

urlpatterns = [
    path('teacher/signup/', views.teacher_signup, name='teacher_signup'),
    path('student/signup/', views.student_signup, name='student_signup'),
    path('teacher/login/', views.teacher_login_view, name='teacher_login'),
    path('student/login/', views.student_login_view, name='student_login'),
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('logout/', views.logout_view, name='logout'),
]