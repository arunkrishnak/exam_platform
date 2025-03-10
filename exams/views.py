from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .forms import PDFUploadForm, ExamCreationForm, QuestionCreationForm, AnswerChoiceFormSet  # Import AnswerChoiceFormSet
from .models import PDFDocument, Exam, Question, StudentExamAttempt, AnswerChoice
from PyPDF2 import PdfReader
from g4f.client import Client
from django.contrib import messages # Import messages framework
from .models import User 
from .models import StudentResponse  # Import the new model
import random
import json
import re
from django.forms import modelform_factory

client = Client()

def extract_text_from_pdf(pdf_file):
    text = ""
    pdf_reader = PdfReader(pdf_file)
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def extract_skills_from_text(text):
    """Extract skills using simple keyword matching or AI-based extraction"""
    skills = set()
    possible_skills = ["Java", "Python", "MySQL", "JavaScript", "C++", "Django", "HTML", "CSS"]  # Extendable skill list
    for skill in possible_skills:
        if skill.lower() in text.lower():
            skills.add(skill)
    return list(skills)

def generate_questions_with_gpt(text, num_questions=3, num_options=4, topic_prompt=""):
    try:
        # Create the prompt based on whether topic_prompt is provided.
        if topic_prompt:
            prompt_text = f"""Generate {num_questions} multiple choice questions on the topic of '{topic_prompt}' from the following text:

{text}

**Formatting Requirements:**

1. Ensure each question is unique and does not repeat concepts.
2. Provide {num_options} distinct answer options per question. 
3. Mark only ONE correct answer clearly.
4. Include real-world examples where appropriate for diversity.

For each question, please follow this structure EXACTLY:

1. **Question Text:** Start with the question number (e.g., "Question 1:") followed by the question itself on a single line. Please ensure the question is clear and concise and relevant to the topic '{topic_prompt}'.

2. **Answer Choices:** Provide exactly {num_options} answer choices. Use lowercase letters (a, b, c, etc.) followed by a period and a space (e.g., {" ".join([f'"{chr(97+i)}. Choice text"' for i in range(num_options)])}). Ensure each choice is unique and plausible, but only one is definitively correct.

3. **Correct Answer:** On a new line after the choices, clearly indicate the correct answer by stating "Correct Answer: " followed by the letter corresponding to the correct choice (e.g., "Correct Answer: {"a" if num_options == 2 else "b"}").

**Example of Desired Output Format:**

Question 1: What is the capital of France?
a. Berlin
b. Paris
c. Rome
d. London
......(As many options as mentioned ie {num_options})
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
......(As many options as mentioned ie {num_options})
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
                    match = re.match(r'^([a-z])\.\s*(.+)$', line)  # Ensure it captures all answer choices dynamically
                    if match:
                        # Even if a choice text accidentally includes "Question" in it, we only consider the letter and text.
                        choice_text = match.group(2).strip()
                        answer_choices.append({'text': choice_text, 'is_correct': False})

            # Mark the correct answer if found.
            if correct_answer_index is not None and 0 <= correct_answer_index < len(answer_choices):
                answer_choices[correct_answer_index]['is_correct'] = True

            questions_data.append({'text': question_text, 'answer_choices': answer_choices})
            questions_data = questions_data[:num_questions]  # Ensure we only return the required number of questions.


        return questions_data

    except Exception as e:
        print(f"GPT Error: {e}")
        return []

@login_required(login_url='teacher_login')
def student_exam_responses(request, student_id, exam_id):
    student = get_object_or_404(User, id=student_id, is_student=True)
    exam = get_object_or_404(Exam, id=exam_id)
    responses = StudentResponse.objects.filter(student=student, exam=exam).select_related('question', 'selected_choice')

    # Calculate total marks (each correct answer = 1 mark)
    total_marks = sum(1 for response in responses if response.selected_choice.is_correct)

    return render(request, 'users/student_exam_responses.html', {
        'student': student,
        'exam': exam,
        'responses': responses,
        'total_marks': total_marks  # Pass total score to the template
    })


@login_required(login_url='teacher_login')
def teacher_dashboard_view(request):
    if not request.user.is_teacher:
        return redirect('home')

    exams = Exam.objects.filter(teacher=request.user)
    student_responses = StudentResponse.objects.filter(exam__in=exams).select_related('student', 'exam')

    if request.method == 'POST':
        exam_form = ExamCreationForm(request.POST, request.FILES)
        
        if exam_form.is_valid():
            exam = exam_form.save(commit=False)
            exam.teacher = request.user
            pdf_file_uploaded = request.FILES.get('pdf_document')

            # Capture skills from user input
            skills_input = exam_form.cleaned_data['skills']
            skills = [skill.strip() for skill in skills_input.split(',') if skill.strip()]
            exam.skills = skills
            exam.save()

            # Generate questions
            num_options = exam_form.cleaned_data['num_options']
            num_questions_per_level = exam_form.cleaned_data['num_questions_per_level']

            # Generate questions for each skill and level
            text = extract_text_from_pdf(pdf_file_uploaded) if pdf_file_uploaded else ""
            unique_questions = set()

            for skill in skills:
                for level in ["Easy", "Medium", "Hard"]:
                    print(f"🔍 Generating questions for {skill} - {level}")
                    
                    # Keep generating until we have enough unique questions
                    while len([q for q in unique_questions if q[1] == level and q[2] == skill]) < num_questions_per_level:
                        generated_questions = generate_questions_with_gpt(
                            text=text,
                            num_questions=num_questions_per_level,
                            num_options=num_options,
                            topic_prompt=f"{skill} - {level}"
                        )

                        for q_data in generated_questions:
                            # Ensure question uniqueness across all skills and levels
                            question_key = (q_data['text'], level, skill)
                            
                            if question_key not in unique_questions:
                                unique_questions.add(question_key)

                                # Save the question with difficulty and skill reference
                                question = Question.objects.create(
                                    exam=exam,
                                    text=q_data['text'],
                                    difficulty=level
                                )

                                for choice_data in q_data.get('answer_choices', []):
                                    AnswerChoice.objects.create(
                                        question=question,
                                        text=choice_data['text'],
                                        is_correct=choice_data['is_correct']
                                    )

                                print(f"✅ Saved Question: '{question.text}' (Difficulty: {question.difficulty})")



            messages.success(request, "Exam created with questions!")
            return redirect('teacher_dashboard')
        else:
            print("❌ Form errors:", exam_form.errors)

    else:
        exam_form = ExamCreationForm()

    student_exam_pairs = set((resp.student, resp.exam) for resp in student_responses)
    student_responses_list = [{'student': s, 'exam': e} for s, e in student_exam_pairs]

    return render(request, 'users/teacher_dashboard.html', {
        'exams': exams,
        'student_responses_list': student_responses_list,
        'exam_creation_form': exam_form,
    })




@login_required(login_url='teacher_login')
def delete_exam(request, exam_id):
    if not request.user.is_teacher:
        return redirect('home')

    exam = get_object_or_404(Exam, id=exam_id, teacher=request.user)

    # Ensure student responses are NOT deleted
    StudentResponse.objects.filter(exam=exam).update(exam=None)

    # Delete the exam AFTER updating student responses
    exam.delete()

    messages.success(request, "Exam deleted successfully! Student responses are retained.")
    return redirect('teacher_dashboard')



@login_required(login_url='teacher_login')
def delete_student_response(request, student_id, exam_id):
    if not request.user.is_teacher:
        return redirect('home')

    student = get_object_or_404(User, id=student_id, is_student=True)
    exam = get_object_or_404(Exam, id=exam_id)

    # Delete the student's responses for this exam
    StudentResponse.objects.filter(student=student, exam=exam).delete()

    messages.success(request, f"Responses for {student.username} in {exam.title} have been deleted.")
    return redirect('teacher_dashboard')

@login_required(login_url='teacher_login')
def view_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    questions = exam.questions.prefetch_related('answer_choices').all()

    return render(request, 'users/view_exam.html', {
        'exam': exam,
        'questions': questions
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
    if request.method == 'POST':
        exam_form = ExamCreationForm(request.POST, request.FILES)
        num_options = int(request.POST.get('num_options', 4))
        num_questions_per_level = int(request.POST.get('num_questions_per_level', 3))
        topic_prompt = request.POST.get('topic_prompt', '')

        if exam_form.is_valid():
            exam = exam_form.save(commit=False)
            exam.teacher = request.user
            pdf_file_uploaded = request.FILES.get('pdf_document')

            if pdf_file_uploaded:
                text = extract_text_from_pdf(pdf_file_uploaded)
                identified_skills = extract_skills_from_text(text)
                exam.skills = identified_skills
                exam.save()

                for skill in identified_skills:
                    for level in ["Easy", "Medium", "Hard"]:
                        generated_questions = generate_questions_with_gpt(
                            text=text, num_questions=num_questions_per_level, num_options=num_options, topic_prompt=f"{skill} - {level}"
                        )

                        for q_data in generated_questions:
                            if q_data.get('text'):
                                question = Question.objects.create(exam=exam, text=q_data['text'])
                                for choice in q_data.get('answer_choices', []):
                                    AnswerChoice.objects.create(question=question, text=choice['text'], is_correct=choice['is_correct'])

                messages.success(request, 'Exam created with questions from detected skills!')
            else:
                exam.save()
                messages.success(request, 'Exam created successfully without auto-generated questions.')

            return redirect('teacher_dashboard')

    else:
        exam_form = ExamCreationForm()

    return render(request, 'exams/create_exam.html', {'exam_form': exam_form})

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
    attempted_exams = Exam.objects.filter(responses__student=request.user).distinct()

    return render(request, 'users/student_dashboard.html', {
        'available_exams': available_exams,
        'attempted_exams': attempted_exams
    })


from django.contrib import messages
from .models import StudentResponse  # Import the new model

@login_required(login_url='student_login')
def take_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)

    if StudentResponse.objects.filter(student=request.user, exam=exam).exists():
        messages.error(request, "You have already attempted this exam.")
        return redirect('student_dashboard')

    questions = list(exam.questions.prefetch_related('answer_choices').all())

    if request.method == 'POST':
        unanswered_questions = []

        for question in questions:
            selected_choice_id = request.POST.get(f"question_{question.id}")
            if not selected_choice_id:
                unanswered_questions.append(question.text)
            else:
                selected_choice = AnswerChoice.objects.get(id=selected_choice_id)
                StudentResponse.objects.create(
                    student=request.user,
                    exam=exam,
                    question=question,
                    selected_choice=selected_choice
                )

        if unanswered_questions:
            messages.error(request, "Please answer all questions before submitting.")
            return redirect('take_exam', exam_id=exam.id)

        messages.success(request, "Exam submitted successfully!")
        return redirect('student_dashboard')

    prepared_questions = []
    for question in questions:
        answer_choices_list = list(question.answer_choices.all())
        random.shuffle(answer_choices_list)
        prepared_questions.append({'question': question, 'answer_choices': answer_choices_list})

    return render(request, 'exams/take_exam.html', {'exam': exam, 'prepared_questions': prepared_questions})

@login_required(login_url='teacher_login')
def edit_question(request, question_id):
    question = get_object_or_404(Question, id=question_id, exam__teacher=request.user)
    QuestionForm = modelform_factory(Question, fields=['text'])
    
    if request.method == 'POST':
        form = QuestionForm(request.POST, instance=question)
        formset = AnswerChoiceFormSet(request.POST, instance=question)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Question updated successfully.")
            return redirect('view_exam', exam_id=question.exam.id)
    else:
        form = QuestionForm(instance=question)
        formset = AnswerChoiceFormSet(instance=question)
    
    return render(request, 'exams/edit_question.html', {
        'question': question,
        'form': form,
        'formset': formset,
    })

def home(request):
    return render(request, 'home.html')