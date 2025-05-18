from django.contrib import admin
from django.urls import path, include
from exams import views

urlpatterns = [
    path('admin/', admin.site.urls), # Admin panel
    path('users/', include('users.urls')),
    path('exams/', include('exams.urls')),
    path('', views.home, name='home'),  # Home page
]