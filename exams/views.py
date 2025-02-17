from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .forms import PDFUploadForm, ExamCreationForm, QuestionCreationForm, AnswerChoiceFormSet  # Import AnswerChoiceFormSet
from .models import PDFDocument, Exam, Question, StudentExamAttempt, AnswerChoice
from PyPDF2 import PdfReader
from g4f.client import Client
from django.utils import timezone
from django.contrib import messages # Import messages framework
import random
import json
import re

client = Client()

def extract_text_from_pdf(pdf_file):
    text = ""
    pdf_reader = PdfReader(pdf_file)
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def generate_questions_with_gpt(text, num_questions=3, num_options=4, topic_prompt=""):
    try:
        # Create the prompt based on whether topic_prompt is provided.
        if topic_prompt:
            prompt_text = f"""Generate {num_questions} multiple choice questions on the topic of '{topic_prompt}' from the following text:

{text}

**Formatting Requirements:**

For each question, please follow this structure EXACTLY:

1. **Question Text:** Start with the question number (e.g., "Question 1:") followed by the question itself on a single line. Please ensure the question is clear and concise and relevant to the topic '{topic_prompt}'.

2. **Answer Choices:** Provide {num_options} answer choices, each on a new line, labeled with lowercase letters followed by a period (e.g., "a. Choice text", "b. Another choice"). Ensure each choice is a plausible answer but only one should be definitively correct.

3. **Correct Answer:** On a new line after the choices, clearly indicate the correct answer by stating "Correct Answer: " followed by the letter corresponding to the correct choice (e.g., "Correct Answer: b").

**Example of Desired Output Format:**

Question 1: What is the capital of France?
a. Berlin
b. Paris
c. Rome
d. London
Correct Answer: b

Question 2: ...
"""
        else:
            prompt_text = f"""Generate {num_questions} multiple choice questions from the following text:

{text}

**Formatting Requirements:**

For each question, please follow this structure EXACTLY:

1. **Question Text:** Start with the question number (e.g., "Question 1:") followed by the question itself on a single line. Please ensure the question is clear and concise.

2. **Answer Choices:** Provide {num_options} answer choices, each on a new line, labeled with lowercase letters followed by a period (e.g., "a. Choice text", "b. Another choice"). Ensure each choice is a plausible answer but only one should be definitively correct.

3. **Correct Answer:** On a new line after the choices, clearly indicate the correct answer by stating "Correct Answer: " followed by the letter corresponding to the correct choice (e.g., "Correct Answer: b").

**Example of Desired Output Format:**

Question 1: What is the capital of France?
a. Berlin
b. Paris
c. Rome
d. London
Correct Answer: b

Question 2: ...
"""

        # Call the GPT model.
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt_text}],
            web_search=False
        )
        gpt_response = response.choices[0].message.content

        # Use regex to split output by lines that begin with "Question <number>:"
        question_blocks = re.split(r'(?=Question\s+\d+:)', gpt_response.strip())
        questions_data = []

        for block in question_blocks:
            block = block.strip()
            if not block:
                continue
            lines = block.splitlines()

            # Process the first line to extract question text (removing the "Question X:" prefix)
            question_line = lines[0]
            question_text = re.sub(r'^Question\s+\d+:\s*', '', question_line).strip()

            answer_choices = []
            correct_answer_index = None

            # Process the remaining lines for answer choices and the correct answer
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                # Check if the line indicates the correct answer
                if line.lower().startswith('correct answer:'):
                    correct_letter = line.split(':', 1)[-1].strip().lower()
                    correct_answer_index = ord(correct_letter) - ord('a')
                else:
                    # Look for lines that start with a letter followed by a period and a space.
                    match = re.match(r'^([a-z])\.\s*(.*)', line)
                    if match:
                        # Even if a choice text accidentally includes "Question" in it, we only consider the letter and text.
                        choice_text = match.group(2).strip()
                        answer_choices.append({'text': choice_text, 'is_correct': False})

            # Mark the correct answer if found.
            if correct_answer_index is not None and 0 <= correct_answer_index < len(answer_choices):
                answer_choices[correct_answer_index]['is_correct'] = True

            questions_data.append({'text': question_text, 'answer_choices': answer_choices})
            if len(questions_data) >= num_questions:  # Stop if we have enough questions.
                break

        return questions_data

    except Exception as e:
        print(f"GPT Error: {e}")
        return []

@login_required(login_url='teacher_login')
def teacher_dashboard_view(request): # Keep teacher dashboard as is, but remove preview from template in next step
    if not request.user.is_teacher:
        return redirect('home')
    pdf_upload_form = PDFUploadForm()
    exam_creation_form = ExamCreationForm()
    uploaded_pdfs = PDFDocument.objects.filter(teacher=request.user)
    exams = Exam.objects.filter(teacher=request.user)
    selected_exam_id = request.GET.get('exam_id')
    selected_exam_questions = None # No preview anymore in template, can remove this logic

    return render(request, 'exams/teacher_dashboard.html', {
        'pdf_upload_form': pdf_upload_form,
        'exam_creation_form': exam_creation_form,
        'uploaded_pdfs': uploaded_pdfs,
        'exams': exams,
        'selected_exam_questions': selected_exam_questions, # Still passing, but not used in template anymore
    })


@login_required(login_url='teacher_login')
def upload_pdf(request): # Keep PDF upload independent for now - might remove later
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_document = form.save(commit=False)
            pdf_document.teacher = request.user
            pdf_document.save()
            messages.success(request, 'PDF uploaded successfully!') # Success message
            return redirect('teacher_dashboard')
        else:
            messages.error(request, 'PDF upload failed. Please check the form.') # Error message
    else:
        form = PDFUploadForm()
    return render(request, 'exams/upload_pdf.html', {'form': form}) # Or handle in dashboard template

@login_required(login_url='teacher_login')
def create_exam(request):
    pdf_upload_form = PDFUploadForm() # For PDF upload form on exam creation page (you might not need this anymore)
    if request.method == 'POST':
        exam_form = ExamCreationForm(request.POST, request.FILES) # Include request.FILES for PDF upload in ExamCreationForm
        num_options = int(request.POST.get('num_options', 4))
        topic_prompt = request.POST.get('topic_prompt', '')
        num_questions = int(request.POST.get('num_questions', 3)) # Get number of questions from form, default to 3


        if exam_form.is_valid():
            exam = exam_form.save(commit=False)
            exam.teacher = request.user

            pdf_file_uploaded = request.FILES.get('pdf_document')
            if pdf_file_uploaded:
                text = extract_text_from_pdf(pdf_file_uploaded)
                generated_questions_data = generate_questions_with_gpt(text, num_options, topic_prompt, num_questions) # Pass num_questions

                exam.save()
                for q_data in generated_questions_data:
                    if q_data and q_data.get('text'):
                        question = Question.objects.create(exam=exam, text=q_data['text'])
                        for choice_data in q_data.get('answer_choices', []):
                            AnswerChoice.objects.create(
                                question=question,
                                text=choice_data['text'],
                                is_correct=choice_data['is_correct']
                            )
                messages.success(request, 'Exam created with questions generated from PDF!')
            else: # If no PDF, just save exam without questions
                exam.save()
                messages.success(request, 'Exam created successfully (no PDF questions generated).')

            return redirect('teacher_dashboard')
        else:
             messages.error(request, 'Exam creation failed. Please check the form.')
    else:
        exam_form = ExamCreationForm()

    return render(request, 'exams/create_exam.html', {'exam_form': exam_form, 'pdf_upload_form': pdf_upload_form}) # Keep pdf_upload_form for now

@login_required(login_url='teacher_login')
def delete_all_pdfs(request):
    PDFDocument.objects.filter(teacher=request.user).delete()
    messages.success(request, 'All your PDFs have been deleted.')
    return redirect('teacher_dashboard')

@login_required(login_url='teacher_login')
def delete_all_exams(request):
    Exam.objects.filter(teacher=request.user).delete()
    messages.success(request, 'All your Exams have been deleted.')
    return redirect('teacher_dashboard')


@login_required(login_url='student_login')
def student_dashboard_view(request):
    if not request.user.is_student:
        return redirect('home')
    available_exams = Exam.objects.all()
    return render(request, 'exams/student_dashboard.html', {'available_exams': available_exams})

@login_required(login_url='student_login')
def take_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    questions = list(exam.questions.prefetch_related('answer_choices').all())
    random.shuffle(questions)

    if request.method == 'POST':
        # ... (rest of your POST request handling) ...
        pass

    # Prepare questions with randomized options for template
    prepared_questions = []
    for question in questions:
        answer_choices_list = list(question.answer_choices.all())
        random.shuffle(answer_choices_list)
        prepared_questions.append({
            'question': question,
            'answer_choices': answer_choices_list,
        })

    print("DEBUG - prepared_questions:", prepared_questions)  # Add this line for debugging

    return render(request, 'exams/take_exam.html', {'exam': exam, 'prepared_questions': prepared_questions})
def home(request):
    return render(request, 'home.html')