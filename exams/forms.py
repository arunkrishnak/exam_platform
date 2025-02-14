from django import forms
from .models import PDFDocument, Exam, Question

class PDFUploadForm(forms.ModelForm):
    class Meta:
        model = PDFDocument
        fields = ['title', 'pdf_file']

class ExamCreationForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ['title', 'description', 'pdf_document']

class QuestionCreationForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'correct_answer']