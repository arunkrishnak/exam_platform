from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from .forms import TeacherSignUpForm, StudentSignUpForm, TeacherLoginForm, StudentLoginForm

def teacher_signup(request):
    if request.method == 'POST':
        form = TeacherSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('teacher_dashboard')
    else:
        form = TeacherSignUpForm()
    return render(request, 'users/teacher_signup.html', {'form': form})

def student_signup(request):
    if request.method == 'POST':
        form = StudentSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('student_dashboard')
    else:
        form = StudentSignUpForm()
    return render(request, 'users/student_signup.html', {'form': form})

def teacher_login_view(request):
    if request.method == 'POST':
        form = TeacherLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('teacher_dashboard')
    else:
        form = TeacherLoginForm()
    return render(request, 'users/teacher_login.html', {'form': form})

def student_login_view(request):
    if request.method == 'POST':
        form = StudentLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('student_dashboard')
    else:
        form = StudentLoginForm()
    return render(request, 'users/student_login.html', {'form': form})

@login_required(login_url='teacher_login')
def teacher_dashboard(request):
    if not request.user.is_teacher:
        return redirect('home')
    return render(request, 'users/teacher_dashboard.html')

@login_required(login_url='student_login')
def student_dashboard(request):
    if not request.user.is_student:
        return redirect('home')
    return render(request, 'users/student_dashboard.html')

def logout_view(request):
    logout(request)
    return redirect('home')