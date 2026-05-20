from flask import Flask, render_template, request, redirect, session
from flask_mysqldb import MySQL
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import os
import pdfplumber
import re

app = Flask(__name__)

# Secret Key
app.secret_key = 'resumeai_secret'

# ================= MYSQL CONFIG =================

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'resume_ats_db'

mysql = MySQL(app)

# ================= HOME PAGE =================

@app.route('/')
def home():
    return render_template('home.html')

# ================= LOGIN PAGE =================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        cursor = mysql.connection.cursor()

        query = """
        SELECT * FROM users
        WHERE email=%s AND password=%s
        """

        values = (email, password)

        cursor.execute(query, values)

        user = cursor.fetchone()

        cursor.close()

        # If User Exists
        if user:

            session['loggedin'] = True
            session['user_id'] = user[0]
            session['fullname'] = user[1]

            return redirect('/dashboard')

        else:
            return "Invalid Email or Password"

    return render_template('login.html')

# ================= REGISTER PAGE =================

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        fullname = request.form['fullname']
        email = request.form['email']
        password = request.form['password']

        cursor = mysql.connection.cursor()

        query = """
        INSERT INTO users(fullname, email, password)
        VALUES(%s, %s, %s)
        """

        values = (fullname, email, password)

        cursor.execute(query, values)

        mysql.connection.commit()

        cursor.close()

        return redirect('/login')

    return render_template('register.html')

# ================= DASHBOARD =================

@app.route('/dashboard')
def dashboard():

    # Check Login Session
    if 'loggedin' in session:

        fullname = session['fullname']

        return render_template(
            'dashboard.html',
            fullname=fullname
        )

    return redirect('/login')

# ================= MULTI RESUME RANKING =================

@app.route('/rank_resumes', methods=['POST'])
def rank_resumes():

    # Check Session
    if 'loggedin' not in session:
        return redirect('/login')

    # Get Job Description
    job_description = request.form['job_description']

    jd_text = job_description.lower()

    jd_text = re.sub(r'[^a-zA-Z0-9 ]', '', jd_text)

    # Get Multiple Files
    resumes = request.files.getlist('resumes')

    results = []

    # Skill List
    skills = [
        "python",
        "java",
        "c",
        "c++",
        "html",
        "css",
        "javascript",
        "flask",
        "django",
        "mysql",
        "sql",
        "machine learning",
        "deep learning",
        "nlp",
        "data science",
        "react"
    ]

    # Process Each Resume
    for resume in resumes:

        # Save File
        filepath = os.path.join(
            'static/uploads',
            resume.filename
        )

        resume.save(filepath)

        # Extract PDF Text
        extracted_text = ""

        try:

            with pdfplumber.open(filepath) as pdf:

                for page in pdf.pages:

                    text = page.extract_text()

                    if text:
                        extracted_text += text

        except:

            extracted_text = ""

        # Skip Empty PDFs
        if extracted_text == "":
            continue

        # Clean Resume Text
        resume_text = extracted_text.lower()

        resume_text = re.sub(
            r'[^a-zA-Z0-9 ]',
            '',
            resume_text
        )

        # ================= SKILL MATCHING =================

        matched_skills = []

        for skill in skills:

            if skill in jd_text and skill in resume_text:

                matched_skills.append(skill)

        # ================= AI SCORE =================

        documents = [resume_text, jd_text]

        cv = CountVectorizer()

        matrix = cv.fit_transform(documents)

        similarity = cosine_similarity(matrix)

        ats_score = round(similarity[0][1] * 100)

        # Store Result
        results.append({

            'filename': resume.filename,

            'score': ats_score,

            'skills': matched_skills

        })

    # ================= SORT BY SCORE =================

    ranked_results = sorted(
        results,
        key=lambda x: x['score'],
        reverse=True
    )

    # ================= SHOW RESULTS =================

    return render_template(
        'ranking.html',
        results=ranked_results
    )

# ================= RESUME UPLOAD + ATS =================

@app.route('/upload_resume', methods=['POST'])
def upload_resume():

    # Check Session
    if 'loggedin' not in session:
        return redirect('/login')

    # Resume File
    resume = request.files['resume']

    # Job Description
    job_description = request.form['job_description']

    if resume:

        # Save Resume
        filepath = os.path.join(
            'static/uploads',
            resume.filename
        )

        resume.save(filepath)

        # ================= EXTRACT TEXT =================

        extracted_text = ""

        try:

            with pdfplumber.open(filepath) as pdf:

                for page in pdf.pages:

                    text = page.extract_text()

                    if text:
                        extracted_text += text

        except:

            extracted_text = ""

        # Skip Empty Resume
        if extracted_text == "":
            return "Unable to read PDF Resume"

        # ================= NLP CLEANING =================

        resume_text = extracted_text.lower()

        jd_text = job_description.lower()

        # Remove Special Characters
        resume_text = re.sub(r'[^a-zA-Z0-9 ]', '', resume_text)
        jd_text = re.sub(r'[^a-zA-Z0-9 ]', '', jd_text)

        # ================= SKILL MATCHING =================

        skills = [
            "python",
            "java",
            "c",
            "c++",
            "html",
            "css",
            "javascript",
            "flask",
            "django",
            "mysql",
            "sql",
            "machine learning",
            "deep learning",
            "nlp",
            "data science",
            "react"
        ]

        matched_skills = []

        missing_skills = []

        for skill in skills:

            # Skill in JD
            if skill in jd_text:

                # Skill found in Resume
                if skill in resume_text:
                    matched_skills.append(skill)

                else:
                    missing_skills.append(skill)

        # ================= AI ATS SCORE =================

        documents = [resume_text, jd_text]

        cv = CountVectorizer()

        matrix = cv.fit_transform(documents)

        similarity = cosine_similarity(matrix)

        ats_score = round(similarity[0][1] * 100)

        # ================= RESULT PAGE =================

        return render_template(
            'ats_result.html',
            score=ats_score,
            matched=matched_skills,
            missing=missing_skills
        )

    return "Upload Failed"

# ================= LOGOUT =================

@app.route('/logout')
def logout():

    session.clear()

    return redirect('/login')

# ================= CONTACT PAGE =================

@app.route('/contact')
def contact():
    return render_template('contact.html')

# ================= RECRUITER PAGE =================

@app.route('/recruiter')
def recruiter():

    if 'loggedin' not in session:
        return redirect('/login')

    return render_template('recruiter.html')

# ================= RUN APP =================

if __name__ == '__main__':
    app.run(debug=True)