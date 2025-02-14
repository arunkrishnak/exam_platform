from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User

class TeacherSignUpForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('is_teacher',)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_teacher = True
        if commit:
            user.save()
        return user

class StudentSignUpForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('is_student',)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_student = True
        if commit:
            user.save()
        return user

class TeacherLoginForm(AuthenticationForm):
    pass

class StudentLoginForm(AuthenticationForm):
    pass