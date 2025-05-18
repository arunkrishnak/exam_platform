from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from .forms import TeacherSignUpForm, StudentSignUpForm, TeacherLoginForm, StudentLoginForm

def teacher_signup(request):
    if request.method == 'POST':        # Check if the form is submitted
        form = TeacherSignUpForm(request.POST)
        if form.is_valid(): # Validate the form
            # Save the user and log them in
            user = form.save()
            login(request, user)
            return redirect('teacher_dashboard')
    else:   # If the request method is GET, create a blank form
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
            if user.is_teacher:  # Ensure only teachers can log in
                login(request, user)
                return redirect('teacher_dashboard')
            else:
                form.add_error(None, "Please enter a correct username and password. Note that both fields may be case-sensitive.")  
    else:
        form = TeacherLoginForm()
    return render(request, 'users/teacher_login.html', {'form': form})


def student_login_view(request):
    if request.method == 'POST':
        form = StudentLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user.is_student:  # Ensure only students can log in
                login(request, user)
                return redirect('student_dashboard')
            else:
                form.add_error(None, "Please enter a correct username and password. Note that both fields may be case-sensitive.")  
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
