from django.urls import path
from . import views

urlpatterns = [
    path('teacher/dashboard/', views.teacher_dashboard_view, name='teacher_dashboard'),
    path('teacher/pdf/upload/', views.upload_pdf, name='upload_pdf'), # Keep PDF upload URL for now
    path('teacher/exam/create/', views.create_exam, name='create_exam'),
    path('teacher/pdf/delete_all/', views.delete_all_pdfs, name='delete_all_pdfs'), # New URL for delete all PDFs
    path('teacher/exam/delete_all/', views.delete_all_exams, name='delete_all_exams'), # New URL for delete all Exams
    path('student/dashboard/', views.student_dashboard_view, name='student_dashboard'),
    path('student/exam/take/<int:exam_id>/', views.take_exam, name='take_exam'),
    path('student/<int:student_id>/performance-by-teacher/', views.student_performance_by_teacher, name='student_performance_by_teacher'),
    path('', views.home, name='home'),
    path('teacher/exam/delete/<int:exam_id>/', views.delete_exam, name='delete_exam'),
    path('teacher/student_response/delete/<int:student_id>/<int:exam_id>/', views.delete_student_response, name='delete_student_response'),
    path('teacher/exam/<int:exam_id>/', views.view_exam, name='view_exam'),
    path('teacher/student_responses/<int:student_id>/<int:exam_id>/', views.student_exam_responses, name='student_exam_responses'),
    path('teacher/question/<int:question_id>/edit/', views.edit_question, name='edit_question'),
    path('teacher/generate_skills/', views.generate_skills_from_pdf, name='generate_skills_from_pdf'), # New URL for generating skills
    path('teacher/feedback/<int:student_id>/<int:exam_id>/', views.add_edit_feedback, name='add_edit_feedback'),
]