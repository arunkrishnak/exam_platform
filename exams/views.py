from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .forms import PDFUploadForm, ExamCreationForm, QuestionCreationForm
from .models import PDFDocument, Exam, Question, StudentExamAttempt
from PyPDF2 import PdfReader
from g4f.client import Client
from django.utils import timezone

client = Client()

def extract_text_from_pdf(pdf_file):
    text = ""
    pdf_reader = PdfReader(pdf_file)
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def generate_questions_with_gpt(text):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": f"Generate 5 multiple choice questions and answers from the following text:\n\n{text}"}],
            web_search=False
        )
        gpt_response = response.choices[0].message.content
        questions = gpt_response.split('\n\n') # Basic split - needs improvement
        return questions
    except Exception as e:
        print(f"GPT Error: {e}")
        return ["Error generating questions from GPT."]

@login_required(login_url='teacher_login')
def teacher_dashboard_view(request):
    if not request.user.is_teacher:
        return redirect('home')
    pdf_upload_form = PDFUploadForm()
    exam_creation_form = ExamCreationForm()
    uploaded_pdfs = PDFDocument.objects.filter(teacher=request.user)
    exams = Exam.objects.filter(teacher=request.user)
    selected_exam_id = request.GET.get('exam_id') # Get exam_id from URL parameter
    selected_exam_questions = None # Initialize to None

    if selected_exam_id:
        try:
            selected_exam = Exam.objects.get(id=selected_exam_id, teacher=request.user)
            selected_exam_questions = selected_exam.questions.all() # Fetch questions for selected exam
        except Exam.DoesNotExist:
            selected_exam = None # Handle case where exam doesn't exist or doesn't belong to teacher
            # Optionally add a message to the user about invalid exam ID

    return render(request, 'exams/teacher_dashboard.html', {
        'pdf_upload_form': pdf_upload_form,
        'exam_creation_form': exam_creation_form,
        'uploaded_pdfs': uploaded_pdfs,
        'exams': exams,
        'selected_exam_questions': selected_exam_questions, # Pass questions to template
    })


@login_required(login_url='teacher_login')
def upload_pdf(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_document = form.save(commit=False)
            pdf_document.teacher = request.user
            pdf_document.save()
            return redirect('teacher_dashboard')
    else:
        form = PDFUploadForm()
    return render(request, 'exams/upload_pdf.html', {'form': form})

@login_required(login_url='teacher_login')
def generate_questions_from_pdf(request, pdf_id):
    pdf_document = get_object_or_404(PDFDocument, id=pdf_id, teacher=request.user)
    pdf_file = pdf_document.pdf_file
    text = extract_text_from_pdf(pdf_file)
    generated_questions_text = generate_questions_with_gpt(text)

    exam = Exam.objects.create(teacher=request.user, title=f"Exam from {pdf_document.title}", pdf_document=pdf_document)
    for q_text in generated_questions_text:
        if q_text.strip():
            Question.objects.create(exam=exam, text=q_text, correct_answer="Answer Placeholder - Parse GPT output")

    return redirect('teacher_dashboard')

@login_required(login_url='teacher_login')
def create_exam(request):
    if request.method == 'POST':
        form = ExamCreationForm(request.POST)
        if form.is_valid():
            exam = form.save(commit=False)
            exam.teacher = request.user
            exam.save()
            return redirect('teacher_dashboard')
    else:
        form = ExamCreationForm()
    return render(request, 'exams/create_exam.html', {'form': form})

@login_required(login_url='student_login')
def student_dashboard_view(request):
    if not request.user.is_student:
        return redirect('home')
    available_exams = Exam.objects.all()
    return render(request, 'exams/student_dashboard.html', {'available_exams': available_exams})

@login_required(login_url='student_login')
def take_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    questions = exam.questions.all()
    if request.method == 'POST':
        student_answers = request.POST
        student_exam_attempt = StudentExamAttempt.objects.create(student=request.user, exam=exam)
        score = 0
        for question in questions:
            student_answer = student_answers.get(f'question_{question.id}', '')
            # Basic GPT Grading (Needs Improvement)
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": f"Question: {question.text}\nCorrect Answer: {question.correct_answer}\nStudent Answer: {student_answer}\nIs the student's answer correct? Answer 'Correct' or 'Incorrect'."}],
                    web_search=False
                )
                gpt_grading = response.choices[0].message.content.strip().lower()
                if "correct" in gpt_grading: # Very basic check
                    score += 1
            except Exception as e:
                print(f"GPT Grading Error: {e}")

        student_exam_attempt.score = (score / questions.count()) * 100 if questions.count() > 0 else 0
        student_exam_attempt.end_time = timezone.now()
        student_exam_attempt.save()
        return redirect('student_dashboard') # In future redirect to results page

    return render(request, 'exams/take_exam.html', {'exam': exam, 'questions': questions})

def home(request):
    return render(request, 'home.html')