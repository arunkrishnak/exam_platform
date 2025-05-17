from django.utils import timezone
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

from collections import defaultdict
from django.db.models import Avg
client = Client()
from django.views.decorators.http import require_POST # Import require_POST

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
            prompt_text = f"""Generate {num_questions} multiple choice questions from the following text:

{text}
{topic_prompt}
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
        # Improved splitting with better handling of empty questions
        question_blocks = [block.strip() for block in re.split(r'(?=Question\s+\d+:)', gpt_response.strip()) if block.strip()]

        questions_data = []

        for block in question_blocks:
            lines = block.splitlines()

            # Ensure the block starts with a valid question
            if not lines or not lines[0].startswith("Question"):
                continue

            # Extract the question text safely
            question_line = lines[0].strip()
            question_text = re.sub(r'^Question\s+\d+:\s*', '', question_line).strip()

            # Ensure valid question text is present
            if not question_text:
                continue

            answer_choices = []
            correct_answer_index = None

            # Process answer choices and find the correct one
            for line in lines[1:]:
                line = line.strip()

                if line.lower().startswith('correct answer:'):
                    correct_letter = line.split(':', 1)[-1].strip().lower()
                    correct_answer_index = ord(correct_letter) - ord('a')
                else:
                    match = re.match(r'^([a-z])\.\s*(.+)$', line)
                    if match:
                        choice_text = match.group(2).strip()
                        answer_choices.append({'text': choice_text, 'is_correct': False})

            # Validate and mark the correct answer
            if correct_answer_index is not None and 0 <= correct_answer_index < len(answer_choices):
                answer_choices[correct_answer_index]['is_correct'] = True

            # Ensure the question has valid answer choices
            if question_text and len(answer_choices) == num_options:
                questions_data.append({'text': question_text, 'answer_choices': answer_choices})

        # Ensure we only return the required number of questions
        questions_data = questions_data[:num_questions]



        return questions_data

    except Exception as e:
        print(f"GPT Error: {e}")
        return []

@login_required # Assuming student login for now
def student_performance_by_teacher(request, student_id):
    """
    Displays a student's exam performance history, grouped by the teacher
    who created each exam, including detailed breakdown per exam.
    """
    student = get_object_or_404(User, id=student_id, is_student=True)

    # Basic authorization
    if request.user.id != student.id and not request.user.is_teacher:
         messages.error(request, "You are not authorized to view this performance history.")
         return redirect('student_dashboard') if request.user.is_student else redirect('home')

    # Get all completed attempts for the student
    attempts = StudentExamAttempt.objects.filter(
        student=student,
        score__isnull=False
    ).select_related('exam', 'exam__teacher').order_by('exam__teacher__username', 'start_time')

    # Get all relevant responses for these attempts in one query
    attempt_exam_ids = [a.exam.id for a in attempts if a.exam]
    all_responses = StudentResponse.objects.filter(
        student=student,
        exam_id__in=attempt_exam_ids
    ).select_related('question', 'selected_choice')

    # Group responses by exam_id for efficient lookup
    responses_by_exam = defaultdict(list)
    for resp in all_responses:
        responses_by_exam[resp.exam_id].append(resp)

    # Group detailed attempts by teacher
    performance_by_teacher = defaultdict(lambda: {'attempts_details': [], 'total_score': 0.0, 'count': 0, 'average_score': 0.0})

    for attempt in attempts:
        if not (attempt.exam and attempt.exam.teacher):
            continue # Skip if exam or teacher is missing

        teacher = attempt.exam.teacher
        exam_responses = responses_by_exam.get(attempt.exam.id, [])

        # Calculate detailed stats for this attempt
        total_marks = 0
        easy_marks, medium_marks, hard_marks = 0, 0, 0
        easy_total, medium_total, hard_total = 0, 0, 0

        for response in exam_responses:
            # Ensure response has a question and selected choice before processing
            if not response.question or not response.selected_choice:
                continue

            difficulty = response.question.difficulty
            is_correct = response.selected_choice.is_correct

            if difficulty.lower() == 'easy':
                easy_total += 1
                if is_correct: easy_marks += 1
            elif difficulty.lower() == 'medium':
                medium_total += 1
                if is_correct: medium_marks += 1
            elif difficulty.lower() == 'hard':
                hard_total += 1
                if is_correct: hard_marks += 1

            if is_correct:
                total_marks += 1 # This might differ from attempt.score if scoring logic changes

        overall_total = easy_total + medium_total + hard_total

        # Determine level classification (using the same 80% threshold logic)
        level = "Needs Improvement"
        # Check division by zero
        if hard_total > 0 and (hard_marks / hard_total) >= 0.8: level = "Advanced"
        elif medium_total > 0 and (medium_marks / medium_total) >= 0.8: level = "Intermediate"
        elif easy_total > 0 and (easy_marks / easy_total) >= 0.8: level = "Beginner"

        # Store attempt and its details
        attempt_details = {
            'attempt': attempt,
            'total_marks': total_marks, # Correct answers count
            'overall_total': overall_total, # Total questions count
            'easy_marks': easy_marks,
            'easy_total': easy_total,
            'medium_marks': medium_marks,
            'medium_total': medium_total,
            'hard_marks': hard_marks,
            'hard_total': hard_total,
            'level': level,
        }
        performance_by_teacher[teacher]['attempts_details'].append(attempt_details)

        # Update teacher's average score calculation
        if attempt.score is not None:
            performance_by_teacher[teacher]['total_score'] += attempt.score
            performance_by_teacher[teacher]['count'] += 1

    # Calculate average score for each teacher
    for teacher, data in performance_by_teacher.items():
        if data['count'] > 0:
            data['average_score'] = round(data['total_score'] / data['count'], 2)

    context = {
        'student': student,
        'performance_data': dict(performance_by_teacher),
    }
    return render(request, 'exams/student_performance_by_teacher.html', context)
@login_required(login_url='teacher_login')
def student_exam_responses(request, student_id, exam_id):
    student = get_object_or_404(User, id=student_id, is_student=True)
    exam = get_object_or_404(Exam, id=exam_id)
    responses = StudentResponse.objects.filter(student=student, exam=exam).select_related('question', 'selected_choice')

    # Initialize topic-wise tracking and overall totals
    topic_data = {}
    total_marks_obtained = 0
    total_possible_marks = 0

    # Helper function to check if the student passed (80% threshold)
    def is_passed(marks, total):
        return total > 0 and (marks / total) >= 0.8

    # Calculate correct responses and totals by topic and difficulty
    for response in responses:
        topic = response.question.topic
        difficulty = response.question.difficulty

        if topic not in topic_data:
            topic_data[topic] = {
                'easy_marks': 0, 'easy_total': 0,
                'medium_marks': 0, 'medium_total': 0,
                'hard_marks': 0, 'hard_total': 0
            }

        # Update totals and correct answers
        if difficulty.lower() == 'easy':
            topic_data[topic]['easy_total'] += 1
            if response.selected_choice and response.selected_choice.is_correct:
                topic_data[topic]['easy_marks'] += 1
        elif difficulty.lower() == 'medium':
            topic_data[topic]['medium_total'] += 1
            if response.selected_choice and response.selected_choice.is_correct:
                topic_data[topic]['medium_marks'] += 1
        elif difficulty.lower() == 'hard':
            topic_data[topic]['hard_total'] += 1
            if response.selected_choice and response.selected_choice.is_correct:
                topic_data[topic]['hard_marks'] += 1

    # Determine student level for each topic and calculate total marks
    for topic, data in topic_data.items():
        total_marks_obtained += data['easy_marks'] + data['medium_marks'] + data['hard_marks']
        total_possible_marks += data['easy_total'] + data['medium_total'] + data['hard_total']

        # Determine the student's level based on progression
        if not is_passed(data['easy_marks'], data['easy_total']):
            data['level'] = "Needs Improvement"
        elif is_passed(data['easy_marks'], data['easy_total']):
            if not is_passed(data['medium_marks'], data['medium_total']):
                data['level'] = "Beginner"
            elif is_passed(data['medium_marks'], data['medium_total']):
                if is_passed(data['hard_marks'], data['hard_total']):
                    data['level'] = "Advanced"
                else:
                    data['level'] = "Intermediate"

    return render(request, 'users/student_exam_responses.html', {
        'student': student,
        'exam': exam,
        'responses': responses,
        'topic_data': topic_data,  # Pass topic-wise data to the template
        'total_marks_obtained': total_marks_obtained,  # Total marks obtained
        'total_possible_marks': total_possible_marks,  # Total marks possible
    })
    
@login_required(login_url='teacher_login')
def student_exam_responses(request, student_id, exam_id):
    student = get_object_or_404(User, id=student_id, is_student=True)
    exam = get_object_or_404(Exam, id=exam_id)
    responses = StudentResponse.objects.filter(student=student, exam=exam).select_related('question', 'selected_choice')

    # Initialize topic-wise tracking and overall totals
    topic_data = {}
    total_marks_obtained = 0
    total_possible_marks = 0

    # Helper function to check if the student passed (80% threshold)
    def is_passed(marks, total):
        return total > 0 and (marks / total) >= 0.8

    # Calculate correct responses and totals by topic and difficulty
    for response in responses:
        topic = response.question.topic
        difficulty = response.question.difficulty

        if topic not in topic_data:
            topic_data[topic] = {
                'easy_marks': 0, 'easy_total': 0,
                'medium_marks': 0, 'medium_total': 0,
                'hard_marks': 0, 'hard_total': 0
            }

        # Update totals and correct answers
        if difficulty.lower() == 'easy':
            topic_data[topic]['easy_total'] += 1
            if response.selected_choice and response.selected_choice.is_correct:
                topic_data[topic]['easy_marks'] += 1
        elif difficulty.lower() == 'medium':
            topic_data[topic]['medium_total'] += 1
            if response.selected_choice and response.selected_choice.is_correct:
                topic_data[topic]['medium_marks'] += 1
        elif difficulty.lower() == 'hard':
            topic_data[topic]['hard_total'] += 1
            if response.selected_choice and response.selected_choice.is_correct:
                topic_data[topic]['hard_marks'] += 1

    # Determine student level for each topic and calculate total marks
    for topic, data in topic_data.items():
        total_marks_obtained += data['easy_marks'] + data['medium_marks'] + data['hard_marks']
        total_possible_marks += data['easy_total'] + data['medium_total'] + data['hard_total']

        # Determine the student's level based on progression
        if not is_passed(data['easy_marks'], data['easy_total']):
            data['level'] = "Needs Improvement"
        elif is_passed(data['easy_marks'], data['easy_total']):
            if not is_passed(data['medium_marks'], data['medium_total']):
                data['level'] = "Beginner"
            elif is_passed(data['medium_marks'], data['medium_total']):
                if is_passed(data['hard_marks'], data['hard_total']):
                    data['level'] = "Advanced"
                else:
                    data['level'] = "Intermediate"

    return render(request, 'users/student_exam_responses.html', {
        'student': student,
        'exam': exam,
        'responses': responses,
        'topic_data': topic_data,  # Pass topic-wise data to the template
        'total_marks_obtained': total_marks_obtained,  # Total marks obtained
        'total_possible_marks': total_possible_marks,  # Total marks possible
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
                                    difficulty=level,
                                    topic=skill 
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
@require_POST
def delete_student_response(request, student_id, exam_id):
    if not request.user.is_teacher:
        return redirect('home')

    student = get_object_or_404(User, id=student_id, is_student=True)
    exam = get_object_or_404(Exam, id=exam_id)

    # Delete the student's responses for this exam
    StudentResponse.objects.filter(student=student, exam=exam).delete()
    # Also delete the StudentExamAttempt to allow retake
    StudentExamAttempt.objects.filter(student=student, exam=exam).delete()

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
                                question = Question.objects.create(
                                    exam=exam,
                                    text=q_data['text'],
                                    difficulty=level  # Ensure the question difficulty is saved
                                )
                                for choice in q_data.get('answer_choices', []):
                                    AnswerChoice.objects.create(
                                        question=question,
                                        text=choice['text'],
                                        is_correct=choice['is_correct']
                                    )

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

from django.utils import timezone # Add this import at the top if not already present

@login_required(login_url='student_login')

def take_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)

    # Check if already fully completed
    existing_attempt = StudentExamAttempt.objects.filter(student=request.user, exam=exam, score__isnull=False).first()
    if existing_attempt:
        messages.error(request, f"You have already completed this exam with a score of {existing_attempt.score:.2f}%.")
        return redirect('student_dashboard')

    questions = list(exam.questions.prefetch_related('answer_choices').all().order_by('difficulty', 'id'))
    grouped_questions = {'easy': [], 'medium': [], 'hard': []}
    for q in questions:
        grouped_questions[q.difficulty.lower()].append(q)

    # Control flow: one question at a time
    current_question_index = int(request.session.get('current_question_index', 0))
    allowed_levels = request.session.get('allowed_levels', ['easy'])

    # Flatten allowed questions only
    allowed_questions = [
        q for level in allowed_levels for q in grouped_questions[level]
    ]
    total_questions = len(allowed_questions)

    # Handle submission
    if request.method == 'POST':
        question_id = request.POST.get('question_id')
        selected_choice_id = request.POST.get('choice')

        if question_id and selected_choice_id:
            question = get_object_or_404(Question, id=question_id)
            selected_choice = get_object_or_404(AnswerChoice, id=selected_choice_id)

            # Save temporary response (session)
            response_data = request.session.get('responses', [])
            response_data.append({
                'question_id': question.id,
                'choice_id': selected_choice.id,
                'level': question.difficulty.lower(),
                'correct': selected_choice.is_correct,
            })
            request.session['responses'] = response_data

            # Advance to next question
            current_question_index += 1
            request.session['current_question_index'] = current_question_index

        # If all questions answered, process and submit
        if current_question_index >= total_questions:
            response_data = request.session.get('responses', [])

            # Score tracking
            level_correct = {'easy': 0, 'medium': 0, 'hard': 0}
            level_total = {'easy': 0, 'medium': 0, 'hard': 0}

            for q in allowed_questions:
                level_total[q.difficulty.lower()] += 1

            responses_to_save = []

            for item in response_data:
                q = get_object_or_404(Question, id=item['question_id'])
                choice = get_object_or_404(AnswerChoice, id=item['choice_id'])

                if item['correct']:
                    level_correct[item['level']] += 1

                responses_to_save.append(StudentResponse(
                    student=request.user,
                    exam=exam,
                    question=q,
                    selected_choice=choice
                ))

            StudentResponse.objects.bulk_create(responses_to_save)

            # Calculate score
            total_score = sum(level_correct.values())
            total_possible = sum(level_total.values())
            score_percent = (total_score / total_possible) * 100 if total_possible > 0 else 0

            # Check eligibility and allow further levels
            eligibility = 'Needs Improvement'
            if level_correct['easy'] >= (level_total['easy'] / 2):
                eligibility = 'Average'
                allowed_levels.append('medium')
            if level_correct['medium'] >= (level_total['medium'] / 2):
                eligibility = 'Excellent'
                allowed_levels.append('hard')

            # Save final attempt
            StudentExamAttempt.objects.update_or_create(
                student=request.user,
                exam=exam,
                defaults={
                    'score': score_percent,
                    'end_time': timezone.now(),
                    'easy_score': level_correct['easy'],
                    'easy_total': level_total['easy'],
                    'medium_score': level_correct['medium'],
                    'medium_total': level_total['medium'],
                    'hard_score': level_correct['hard'],
                    'hard_total': level_total['hard'],
                    'eligibility': eligibility
                }
            )

            # Clear session
            request.session.pop('responses', None)
            request.session.pop('current_question_index', None)
            request.session.pop('allowed_levels', None)

            # Show result message
            if 'medium' not in allowed_levels:
                messages.warning(request, "You did not pass the easy section, so medium and hard sections were not attempted.")
            elif 'hard' not in allowed_levels:
                messages.warning(request, "You did not pass the medium section, so hard section was not attempted.")
            else:
                messages.success(request, f"Exam submitted successfully! Your score: {score_percent:.2f}%")

            return redirect('student_dashboard')

    # Render current question
    if current_question_index < total_questions:
        question = allowed_questions[current_question_index]
        return render(request, 'exams/take_exam.html', {
            'exam': exam,
            'question': question,
            'answer_choices': question.answer_choices.all(),
            'question_index': current_question_index + 1,
            'total_questions': total_questions,
            'level': question.difficulty,
        })

    return redirect('student_dashboard')  # fallback
        
def finalize_exam(request, exam, questions):
    level_correct = request.session.get('level_correct', {})
    level_total = request.session.get('level_total', {})
    allowed_levels = request.session.get('allowed_levels', [])

    total_score = sum(level_correct.get(lvl, 0) for lvl in ['easy', 'medium', 'hard'])
    total_possible = sum(level_total.get(lvl, 0) for lvl in ['easy', 'medium', 'hard'])

    score_percent = (total_score / total_possible) * 100 if total_possible > 0 else 0

    StudentExamAttempt.objects.update_or_create(
        student=request.user,
        exam=exam,
        defaults={
            'score': score_percent,
            'end_time': timezone.now(),
            'easy_score': level_correct.get('easy', 0),
            'easy_total': level_total.get('easy', 0),
            'medium_score': level_correct.get('medium', 0),
            'medium_total': level_total.get('medium', 0),
            'hard_score': level_correct.get('hard', 0),
            'hard_total': level_total.get('hard', 0),
            'eligibility': 'Needs Improvement' if 'medium' not in allowed_levels else (
                'Average' if 'hard' not in allowed_levels else 'Excellent'
            )
        }
    )

    # Clear session data
    for key in ['question_index', 'level_correct', 'level_total', 'allowed_levels']:
        if key in request.session:
            del request.session[key]

    if 'medium' not in allowed_levels:
        messages.warning(request, "You did not pass the easy section, so medium and hard sections were not attempted.")
    elif 'hard' not in allowed_levels:
        messages.warning(request, "You did not pass the medium section, so hard section was not attempted.")
    else:
        messages.success(request, f"Exam submitted successfully! Your score: {score_percent:.2f}%")

    return redirect('student_dashboard')


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