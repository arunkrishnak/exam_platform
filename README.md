# Online Exam Platform

This project is a web-based online exam platform built with Django. It provides functionalities for teachers to create and manage exams, and for students to take exams and view their performance.

## Features

*   **Teacher Features:**
    *   Teacher registration and login
    *   Create new exams
    *   Add and edit questions for exams
    *   Upload PDF documents related to exams
    *   View student performance on exams
    *   Provide feedback on student attempts
*   **Student Features:**
    *   Student registration and login
    *   View available exams
    *   Take exams
    *   View exam responses and feedback
    *   View performance dashboard

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd django
    ```
    *(Replace `<repository_url>` with the actual repository URL)*

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Apply database migrations:**
    ```bash
    python manage.py migrate
    ```

5.  **Create a superuser (for admin access):**
    ```bash
    python manage.py createsuperuser
    ```
    *(Follow the prompts to create a username, email, and password)*

6.  **Run the development server:**
    ```bash
    python manage.py runserver
    ```

The application will be available at `http://127.0.0.1:8000/`.

## Usage

*   Navigate to `http://127.0.0.1:8000/` in your web browser.
*   Teachers can sign up/log in via the teacher login page.
*   Students can sign up/log in via the student login page.
*   Explore the teacher and student dashboards to access features.

## Project Structure

```
.
├── manage.py
├── requirements.txt
├── exams/
│   ├── forms.py
│   ├── models.py
│   ├── urls.py
│   ├── views.py
│   └── migrations/
├── my_exam_website/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── templates/
│   ├── base.html
│   ├── home.html
└── users/
    ├── forms.py
    ├── models.py
    ├── urls.py
    ├── views.py
    └── migrations/
```

## Technologies Used

*   Python
*   Django
*   HTML
*   CSS
*   JavaScript
*   SQLite (default database)
