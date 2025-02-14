from django.urls import path
from . import views

urlpatterns = [
    path('teacher/dashboard/', views.teacher_dashboard_view, name='teacher_dashboard'),
    path('teacher/pdf/upload/', views.upload_pdf, name='upload_pdf'),
    path('teacher/pdf/generate_questions/<int:pdf_id>/', views.generate_questions_from_pdf, name='generate_questions_from_pdf'),
    path('teacher/exam/create/', views.create_exam, name='create_exam'),
    path('student/dashboard/', views.student_dashboard_view, name='student_dashboard'),
    path('student/exam/take/<int:exam_id>/', views.take_exam, name='take_exam'),
    path('', views.home, name='home'),
]