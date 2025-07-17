from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
import os
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from quizmaster.extensions import db
from quizmaster.forms import RegistrationForm, LoginForm, QuizForm, QuestionForm, OptionForm, SubjectForm, ChapterForm
from datetime import datetime, timedelta
from flask import session
from flask import abort

login_manager = LoginManager()
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quizmaster.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Import models here to avoid circular import
    from quizmaster.models import User, Quiz, Attempt, Question, Option, AttemptAnswer, Subject, Chapter

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # All route definitions go here, using 'app.route' and referencing models/forms as needed
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        form = RegistrationForm()
        if form.validate_on_submit():
            if User.query.filter_by(email=form.email.data).first():
                flash('Email already registered.', 'danger')
                return render_template('register.html', form=form)
            user = User(
                email=form.email.data,
                full_name=form.full_name.data,
                qualification=form.qualification.data,
                dob=form.dob.data,
                is_admin=False
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        return render_template('register.html', form=form)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data).first()
            if user and user.check_password(form.password.data):
                login_user(user, remember=form.remember.data)
                flash('Logged in successfully.', 'success')
                next_page = request.args.get('next')
                return redirect(next_page or url_for('dashboard'))
            else:
                flash('Invalid email or password.', 'danger')
        return render_template('login.html', form=form)

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('login'))

    @app.route('/dashboard', methods=['GET', 'POST'])
    @login_required
    def dashboard():
        subjects = Subject.query.all()
        selected_subject_id = request.form.get('subject')
        selected_chapter_id = request.form.get('chapter')
        chapters = Chapter.query.filter_by(subject_id=selected_subject_id).all() if selected_subject_id else []
        quizzes = []
        if selected_chapter_id:
            quizzes = Quiz.query.filter_by(chapter_id=selected_chapter_id).all()
        attempts = Attempt.query.filter_by(user_id=current_user.id).order_by(Attempt.completed_at.desc()).all()
        attempts_data = []
        for a in attempts:
            max_score = len(a.quiz.questions)
            percent = int((a.score or 0) / (max_score or 1) * 100)
            attempts_data.append({
                'quiz': a.quiz,
                'score': a.score or 0,
                'max_score': max_score or 1,
                'percent': percent,
                'duration': a.duration or 0,
                'completed_at': a.completed_at or datetime.utcnow()
            })
        return render_template('dashboard.html',
            subjects=subjects,
            chapters=chapters,
            quizzes=quizzes,
            selected_subject_id=selected_subject_id,
            selected_chapter_id=selected_chapter_id,
            attempts=attempts_data)

    @app.route('/quiz/<int:quiz_id>', methods=['GET', 'POST'])
    @login_required
    def take_quiz(quiz_id):
        quiz = Quiz.query.get_or_404(quiz_id)
        questions = quiz.questions
        if not questions:
            flash('No questions in this quiz.', 'warning')
            return redirect(url_for('dashboard'))
        # Session state for quiz progress
        if 'quiz_progress' not in session or session.get('quiz_id') != quiz_id:
            session['quiz_progress'] = {}
            session['quiz_id'] = quiz_id
            session['current_index'] = 0
        if request.method == 'POST':
            selected_option = request.form.get('selected_option')
            current_index = session['current_index']
            if selected_option:
                session['quiz_progress'][str(questions[current_index].id)] = int(selected_option)
            action = request.form.get('action')
            if action == 'next' and current_index < len(questions) - 1:
                session['current_index'] += 1
            elif action == 'prev' and current_index > 0:
                session['current_index'] -= 1
            elif action == 'submit':
                # Calculate score
                score = 0
                answers = []
                for q in questions:
                    selected = session['quiz_progress'].get(str(q.id))
                    if selected and q.correct_option_id == selected:
                        score += 1
                    answers.append({'question_id': q.id, 'selected_option_id': selected})
                attempt = Attempt(user_id=current_user.id, quiz_id=quiz.id, score=score, completed_at=datetime.utcnow(), duration=quiz.duration*60)
                db.session.add(attempt)
                db.session.commit()
                for ans in answers:
                    db.session.add(AttemptAnswer(attempt_id=attempt.id, question_id=ans['question_id'], selected_option_id=ans['selected_option_id']))
                db.session.commit()
                session.pop('quiz_progress', None)
                session.pop('quiz_id', None)
                session.pop('current_index', None)
                flash(f'Quiz submitted! Your score: {score}/{len(questions)}', 'success')
                return redirect(url_for('dashboard'))
        current_index = session.get('current_index', 0)
        question = questions[current_index]
        selected_option = session['quiz_progress'].get(str(question.id)) if 'quiz_progress' in session else None
        return render_template('quiz.html', quiz=quiz, questions=questions, current_index=current_index, question=question, selected_option=selected_option)

    @app.route('/admin/quizzes')
    @login_required
    def admin_quizzes():
        if not current_user.is_admin:
            abort(403)
        quizzes = Quiz.query.all()
        return render_template('admin/manage_quizzes.html', quizzes=quizzes)

    @app.route('/admin/quizzes/add', methods=['GET', 'POST'])
    @login_required
    def add_quiz():
        if not current_user.is_admin:
            abort(403)
        form = QuizForm()
        if form.validate_on_submit():
            quiz = Quiz(
                title=form.title.data,
                description=form.description.data,
                category=form.category.data,
                difficulty=form.difficulty.data,
                duration=form.duration.data
            )
            db.session.add(quiz)
            db.session.commit()
            flash('Quiz added successfully.', 'success')
            return redirect(url_for('admin_quizzes'))
        return render_template('admin/edit_quiz.html', form=form, action='Add')

    @app.route('/admin/quizzes/edit/<int:quiz_id>', methods=['GET', 'POST'])
    @login_required
    def edit_quiz(quiz_id):
        if not current_user.is_admin:
            abort(403)
        quiz = Quiz.query.get_or_404(quiz_id)
        form = QuizForm(obj=quiz)
        if form.validate_on_submit():
            quiz.title = form.title.data
            quiz.description = form.description.data
            quiz.category = form.category.data
            quiz.difficulty = form.difficulty.data
            quiz.duration = form.duration.data
            db.session.commit()
            flash('Quiz updated successfully.', 'success')
            return redirect(url_for('admin_quizzes'))
        return render_template('admin/edit_quiz.html', form=form, action='Edit')

    @app.route('/admin/quizzes/delete/<int:quiz_id>')
    @login_required
    def delete_quiz(quiz_id):
        if not current_user.is_admin:
            abort(403)
        quiz = Quiz.query.get_or_404(quiz_id)
        db.session.delete(quiz)
        db.session.commit()
        flash('Quiz deleted.', 'info')
        return redirect(url_for('admin_quizzes'))

    @app.route('/admin/quizzes/<int:quiz_id>/questions')
    @login_required
    def manage_questions(quiz_id):
        if not current_user.is_admin:
            abort(403)
        quiz = Quiz.query.get_or_404(quiz_id)
        questions = quiz.questions
        return render_template('admin/manage_questions.html', quiz=quiz, questions=questions)

    @app.route('/admin/quizzes/<int:quiz_id>/questions/add', methods=['GET', 'POST'])
    @login_required
    def add_question(quiz_id):
        if not current_user.is_admin:
            abort(403)
        quiz = Quiz.query.get_or_404(quiz_id)
        form = QuestionForm()
        # Set correct_option choices dynamically
        form.correct_option.choices = [(i, f'Option {i+1}') for i in range(len(form.options))]
        if form.validate_on_submit():
            question = Question(quiz_id=quiz.id, text=form.text.data)
            db.session.add(question)
            db.session.flush()  # Get question.id
            options = []
            for option_form in form.options:
                option = Option(question_id=question.id, text=option_form.text.data)
                db.session.add(option)
                options.append(option)
            db.session.flush()
            correct_index = form.correct_option.data
            if 0 <= correct_index < len(options):
                question.correct_option_id = options[correct_index].id
            db.session.commit()
            flash('Question added successfully.', 'success')
            return redirect(url_for('manage_questions', quiz_id=quiz.id))
        return render_template('admin/edit_question.html', form=form, quiz=quiz, action='Add')

    @app.route('/admin/quizzes/<int:quiz_id>/questions/edit/<int:question_id>', methods=['GET', 'POST'])
    @login_required
    def edit_question(quiz_id, question_id):
        if not current_user.is_admin:
            abort(403)
        quiz = Quiz.query.get_or_404(quiz_id)
        question = Question.query.get_or_404(question_id)
        options = question.options
        form = QuestionForm(obj=question)
        # Populate options
        while len(form.options) < len(options):
            form.options.append_entry()
        for i, option in enumerate(options):
            form.options[i].text.data = option.text
        form.correct_option.choices = [(i, f'Option {i+1}') for i in range(len(options))]
        if question.correct_option_id:
            for idx, option in enumerate(options):
                if option.id == question.correct_option_id:
                    form.correct_option.data = idx
        if form.validate_on_submit():
            question.text = form.text.data
            for i, option_form in enumerate(form.options):
                if i < len(options):
                    options[i].text = option_form.text.data
            correct_index = form.correct_option.data
            if 0 <= correct_index < len(options):
                question.correct_option_id = options[correct_index].id
            db.session.commit()
            flash('Question updated successfully.', 'success')
            return redirect(url_for('manage_questions', quiz_id=quiz.id))
        return render_template('admin/edit_question.html', form=form, quiz=quiz, action='Edit')

    @app.route('/admin/quizzes/<int:quiz_id>/questions/delete/<int:question_id>')
    @login_required
    def delete_question(quiz_id, question_id):
        if not current_user.is_admin:
            abort(403)
        question = Question.query.get_or_404(question_id)
        db.session.delete(question)
        db.session.commit()
        flash('Question deleted.', 'info')
        return redirect(url_for('manage_questions', quiz_id=quiz_id))

    @app.route('/admin/subjects')
    @login_required
    def manage_subjects():
        if not current_user.is_admin:
            abort(403)
        subjects = Subject.query.all()
        return render_template('admin/manage_subjects.html', subjects=subjects)

    @app.route('/admin/subjects/add', methods=['GET', 'POST'])
    @login_required
    def add_subject():
        if not current_user.is_admin:
            abort(403)
        form = SubjectForm()
        if form.validate_on_submit():
            subject = Subject(name=form.name.data, description=form.description.data)
            db.session.add(subject)
            db.session.commit()
            flash('Subject added successfully.', 'success')
            return redirect(url_for('manage_subjects'))
        return render_template('admin/edit_subject.html', form=form, action='Add')

    @app.route('/admin/subjects/edit/<int:subject_id>', methods=['GET', 'POST'])
    @login_required
    def edit_subject(subject_id):
        if not current_user.is_admin:
            abort(403)
        subject = Subject.query.get_or_404(subject_id)
        form = SubjectForm(obj=subject)
        if form.validate_on_submit():
            subject.name = form.name.data
            subject.description = form.description.data
            db.session.commit()
            flash('Subject updated successfully.', 'success')
            return redirect(url_for('manage_subjects'))
        return render_template('admin/edit_subject.html', form=form, action='Edit')

    @app.route('/admin/subjects/delete/<int:subject_id>')
    @login_required
    def delete_subject(subject_id):
        if not current_user.is_admin:
            abort(403)
        subject = Subject.query.get_or_404(subject_id)
        db.session.delete(subject)
        db.session.commit()
        flash('Subject deleted.', 'info')
        return redirect(url_for('manage_subjects'))

    @app.route('/admin/subjects/<int:subject_id>/chapters')
    @login_required
    def manage_chapters(subject_id):
        if not current_user.is_admin:
            abort(403)
        subject = Subject.query.get_or_404(subject_id)
        chapters = subject.chapters
        return render_template('admin/manage_chapters.html', subject=subject, chapters=chapters)

    @app.route('/admin/subjects/<int:subject_id>/chapters/add', methods=['GET', 'POST'])
    @login_required
    def add_chapter(subject_id):
        if not current_user.is_admin:
            abort(403)
        subject = Subject.query.get_or_404(subject_id)
        form = ChapterForm()
        if form.validate_on_submit():
            chapter = Chapter(subject_id=subject.id, name=form.name.data, description=form.description.data)
            db.session.add(chapter)
            db.session.commit()
            flash('Chapter added successfully.', 'success')
            return redirect(url_for('manage_chapters', subject_id=subject.id))
        return render_template('admin/edit_chapter.html', form=form, subject=subject, action='Add')

    @app.route('/admin/subjects/<int:subject_id>/chapters/edit/<int:chapter_id>', methods=['GET', 'POST'])
    @login_required
    def edit_chapter(subject_id, chapter_id):
        if not current_user.is_admin:
            abort(403)
        subject = Subject.query.get_or_404(subject_id)
        chapter = Chapter.query.get_or_404(chapter_id)
        form = ChapterForm(obj=chapter)
        if form.validate_on_submit():
            chapter.name = form.name.data
            chapter.description = form.description.data
            db.session.commit()
            flash('Chapter updated successfully.', 'success')
            return redirect(url_for('manage_chapters', subject_id=subject.id))
        return render_template('admin/edit_chapter.html', form=form, subject=subject, action='Edit')

    @app.route('/admin/subjects/<int:subject_id>/chapters/delete/<int:chapter_id>')
    @login_required
    def delete_chapter(subject_id, chapter_id):
        if not current_user.is_admin:
            abort(403)
        chapter = Chapter.query.get_or_404(chapter_id)
        db.session.delete(chapter)
        db.session.commit()
        flash('Chapter deleted.', 'info')
        return redirect(url_for('manage_chapters', subject_id=subject_id))

    @app.route('/admin/chapters/<int:chapter_id>/quizzes')
    @login_required
    def manage_quizzes(chapter_id):
        if not current_user.is_admin:
            abort(403)
        chapter = Chapter.query.get_or_404(chapter_id)
        quizzes = chapter.quizzes
        return render_template('admin/manage_quizzes.html', chapter=chapter, quizzes=quizzes)

    @app.route('/admin/chapters/<int:chapter_id>/quizzes/add', methods=['GET', 'POST'])
    @login_required
    def add_quiz_to_chapter(chapter_id):
        if not current_user.is_admin:
            abort(403)
        chapter = Chapter.query.get_or_404(chapter_id)
        form = QuizForm()
        form.chapter_id.data = chapter.id
        if form.validate_on_submit():
            quiz = Quiz(
                chapter_id=chapter.id,
                title=form.title.data,
                description=form.description.data,
                date_of_quiz=form.date_of_quiz.data,
                time_duration=form.time_duration.data,
                remarks=form.remarks.data,
                difficulty=form.difficulty.data
            )
            db.session.add(quiz)
            db.session.commit()
            flash('Quiz added successfully.', 'success')
            return redirect(url_for('manage_quizzes', chapter_id=chapter.id))
        return render_template('admin/edit_quiz.html', form=form, chapter=chapter, action='Add')

    @app.route('/admin/chapters/<int:chapter_id>/quizzes/edit/<int:quiz_id>', methods=['GET', 'POST'])
    @login_required
    def edit_quiz_in_chapter(chapter_id, quiz_id):
        if not current_user.is_admin:
            abort(403)
        chapter = Chapter.query.get_or_404(chapter_id)
        quiz = Quiz.query.get_or_404(quiz_id)
        form = QuizForm(obj=quiz)
        form.chapter_id.data = chapter.id
        if form.validate_on_submit():
            quiz.title = form.title.data
            quiz.description = form.description.data
            quiz.date_of_quiz = form.date_of_quiz.data
            quiz.time_duration = form.time_duration.data
            quiz.remarks = form.remarks.data
            quiz.difficulty = form.difficulty.data
            db.session.commit()
            flash('Quiz updated successfully.', 'success')
            return redirect(url_for('manage_quizzes', chapter_id=chapter.id))
        return render_template('admin/edit_quiz.html', form=form, chapter=chapter, action='Edit')

    @app.route('/admin/chapters/<int:chapter_id>/quizzes/delete/<int:quiz_id>')
    @login_required
    def delete_quiz_in_chapter(chapter_id, quiz_id):
        if not current_user.is_admin:
            abort(403)
        quiz = Quiz.query.get_or_404(quiz_id)
        db.session.delete(quiz)
        db.session.commit()
        flash('Quiz deleted.', 'info')
        return redirect(url_for('manage_quizzes', chapter_id=chapter_id))

    @app.route('/admin/dashboard', methods=['GET', 'POST'])
    @login_required
    def admin_dashboard():
        if not current_user.is_admin:
            abort(403)
        stats = {
            'users': User.query.filter_by(is_admin=False).count(),
            'subjects': Subject.query.count(),
            'chapters': Chapter.query.count(),
            'quizzes': Quiz.query.count(),
            'attempts': Attempt.query.count()
        }
        search_type = request.form.get('search_type')
        search_query = request.form.get('search_query', '').strip()
        results = []
        if search_type and search_query:
            if search_type == 'user':
                results = User.query.filter(User.email.ilike(f'%{search_query}%')).all()
            elif search_type == 'subject':
                results = Subject.query.filter(Subject.name.ilike(f'%{search_query}%')).all()
            elif search_type == 'quiz':
                results = Quiz.query.filter(Quiz.title.ilike(f'%{search_query}%')).all()
        return render_template('admin/admin_dashboard.html', stats=stats, search_type=search_type, search_query=search_query, results=results)

    with app.app_context():
        db.create_all()
        # Seed admin account if not exists
        admin = User.query.filter_by(is_admin=True).first()
        if not admin:
            admin = User(
                email='admin@quiz.com',
                full_name='Quiz Master Admin',
                qualification='Administrator',
                dob=None,
                is_admin=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()

    return app 

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True) 