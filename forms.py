from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, IntegerField, SelectField, FieldList, FormField, HiddenField, DateField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, NumberRange

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    full_name = StringField('Full Name', validators=[DataRequired()])
    qualification = StringField('Qualification', validators=[DataRequired()])
    dob = DateField('Date of Birth', format='%Y-%m-%d', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Repeat Password', validators=[DataRequired(), EqualTo('password')])
    is_admin = BooleanField('Register as Admin')
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class OptionForm(FlaskForm):
    text = StringField('Option Text', validators=[DataRequired()])

class QuestionForm(FlaskForm):
    text = TextAreaField('Question', validators=[DataRequired()])
    options = FieldList(FormField(OptionForm), min_entries=4, max_entries=6)
    correct_option = SelectField('Correct Option', coerce=int)

class QuizForm(FlaskForm):
    title = StringField('Quiz Title', validators=[DataRequired()])
    description = TextAreaField('Description')
    date_of_quiz = DateField('Date of Quiz', format='%Y-%m-%d', validators=[], default=None)
    time_duration = StringField('Time Duration (hh:mm)', validators=[Length(max=8)])
    remarks = TextAreaField('Remarks')
    difficulty = SelectField('Difficulty', choices=[('Easy','Easy'),('Medium','Medium'),('Hard','Hard')])
    chapter_id = HiddenField('Chapter ID')
    submit = SubmitField('Save Quiz')

class SubjectForm(FlaskForm):
    name = StringField('Subject Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    submit = SubmitField('Save Subject')

class ChapterForm(FlaskForm):
    name = StringField('Chapter Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    submit = SubmitField('Save Chapter') 