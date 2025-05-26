from django import forms
from .models import PDFDocument, Exam, Question, AnswerChoice
from django.forms import inlineformset_factory

class PDFUploadForm(forms.ModelForm): # Keep PDF upload form for now
    class Meta:
        model = PDFDocument
        fields = ['title', 'pdf_file']

class ExamCreationForm(forms.ModelForm):
    pdf_document = forms.FileField(required=False, label="Upload PDF (Optional)")
    num_options = forms.IntegerField(min_value=2, max_value=5, initial=4, label="Number of Answer Options per Question")
    topic_prompt = forms.CharField(widget=forms.Textarea, required=False, label="Topic Prompt (Optional)")
    num_questions_per_level = forms.IntegerField(min_value=1, max_value=10, initial=3, label="Number of Questions per Level")
    skills = forms.CharField(required=True, label="Sub topics (comma-separated)")
    num_skills_to_generate = forms.IntegerField(min_value=1, required=False, initial=5, label="Number of Sub topics to Auto-Generate (Optional)")

    class Meta:
        model = Exam
        fields = ['title', 'description']


# Base form for AnswerChoice - will be used in formset
class AnswerChoiceForm(forms.ModelForm):
    class Meta:
        model = AnswerChoice
        fields = ['text', 'is_correct']

AnswerChoiceFormSet = inlineformset_factory(Question, AnswerChoice, form=AnswerChoiceForm, extra=4, can_delete=True)

class QuestionCreationForm(forms.ModelForm): # We might not use this directly anymore for MCQ creation
    class Meta:
        model = Question
        fields = ['text', 'difficulty']