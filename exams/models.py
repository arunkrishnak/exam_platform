from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model() 
class PDFDocument(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'is_teacher': True})
    title = models.CharField(max_length=255)
    pdf_file = models.FileField(upload_to='pdfs/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
    
class StudentResponse(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'is_student': True})
    exam = models.ForeignKey('Exam', on_delete=models.SET_NULL, null=True, blank=True, related_name="responses")  # ✅ Allow NULL
    question = models.ForeignKey('Question', on_delete=models.CASCADE)
    selected_choice = models.ForeignKey('AnswerChoice', on_delete=models.SET_NULL, null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.username} - {self.exam.title if self.exam else 'Exam Deleted'} - {self.question.text[:30]}"


class Exam(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'is_teacher': True})
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    pdf_document = models.FileField(upload_to='pdfs/', null=True, blank=True)
    skills = models.JSONField(default=list)  # Store skills as a list
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title



class Question(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    difficulty = models.CharField(max_length=10, choices=[('Easy', 'Easy'), ('Medium', 'Medium'), ('Hard', 'Hard')])
    topic = models.CharField(max_length=255)  # Add this field to track topics

    def __str__(self):
        return self.text


class AnswerChoice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answer_choices')
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text[:100] + "..."

class StudentExamAttempt(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'is_student': True})
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True)
    
    easy_score = models.IntegerField(default=0)
    easy_total = models.IntegerField(default=0)
    medium_score = models.IntegerField(default=0)
    medium_total = models.IntegerField(default=0)
    hard_score = models.IntegerField(default=0)
    hard_total = models.IntegerField(default=0)
    eligibility = models.CharField(max_length=20, default='Needs Improvement')

    def __str__(self):
        return f"{self.student.username} - {self.exam.title}"