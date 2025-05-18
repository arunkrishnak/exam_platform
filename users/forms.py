from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User

#Defines logic to create and identify teacher/student accounts.

class TeacherSignUpForm(UserCreationForm): # Extends Django's default UserCreationForm and uses your custom User model.
    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('is_teacher',)

    def save(self, commit=True):            # Overrides the save method to mark the user as a teacher before saving.
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