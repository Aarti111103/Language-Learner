
from flask import Flask, render_template, request, send_from_directory, redirect, url_for, session
import os
from model import SpellCheckerModule
from datetime import datetime
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from functools import wraps
from googletrans import Translator
import requests
from transformers import pipeline
import re

app = Flask(__name__)
app.secret_key = 'supersecret'
spell_checker_module = SpellCheckerModule()
translator_module = Translator()

# MySQL Config
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '1016'  # Update if you have a password
app.config['MYSQL_DB'] = 'grammar_app'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)
bcrypt = Bcrypt(app)

DOWNLOAD_FOLDER = 'downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Decorator for login required
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            return redirect(url_for('signin'))
    return wrap

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                    (username, email, hashed_pw))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('signin'))

    return render_template('signup.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cur.fetchone()
        cur.close()

        if user and bcrypt.check_password_hash(user['password'], password):
            session['logged_in'] = True
            session['username'] = user['username']
            session['user_id'] = user['id']
            return redirect(url_for('dashboard'))
        else:
            return "Login Failed: Invalid credentials"

    return render_template('signin.html')

@app.route('/signout')
def signout():
    session.clear()
    return redirect(url_for('signin'))

@app.route('/spell', methods=['POST'])
@login_required
def spell():
    try:
        text = request.form['text']
        corrected_text = spell_checker_module.correct_spell(text)
        corrected_grammar_text, grammar_details = spell_checker_module.correct_grammar(corrected_text)

        session['last_corrected'] = corrected_grammar_text
        session['last_filename'] = 'typed_text.txt'

        return render_template('index.html', corrected_text=corrected_grammar_text, grammar_issues=grammar_details)
    except Exception as e:
        print("Error in /spell route:", e)
        return "An error occurred: " + str(e), 500

@app.route('/grammar', methods=['POST'])
@login_required
def grammar():
    try:
        file = request.files['file']
        original_filename = file.filename or "uploaded_file.txt"
        readable_file = file.read().decode('utf-8', errors='ignore')

        corrected_file_text = spell_checker_module.correct_spell(readable_file)
        corrected_file_grammar, grammar_details = spell_checker_module.correct_grammar(corrected_file_text)

        session['last_corrected'] = corrected_file_grammar
        session['last_filename'] = original_filename

        return render_template('index.html', corrected_file_text=corrected_file_grammar, corrected_file_grammar=grammar_details)
    except Exception as e:
        print("Error in /grammar route:", e)
        return "File upload error: " + str(e), 500

@app.route('/speak', methods=['GET'])
@login_required
def speak():
    try:
        voice_text = spell_checker_module.voice_to_text()
        corrected_text = spell_checker_module.correct_spell(voice_text)
        corrected_grammar_text, grammar_details = spell_checker_module.correct_grammar(corrected_text)

        session['last_corrected'] = corrected_grammar_text
        session['last_filename'] = 'voice_input.txt'

        return render_template('index.html', corrected_text=corrected_grammar_text, grammar_issues=grammar_details, voice_input=voice_text)
    except Exception as e:
        print("Voice input error:", e)
        return "Voice error: " + str(e), 500

@app.route('/download', methods=['POST'])
@login_required
def download():
    text = session.get('last_corrected', '')
    original_name = session.get('last_filename', 'corrected')

    if not text:
        return redirect(url_for('index'))

    base_name = os.path.splitext(original_name)[0]
    filename = f"{base_name}_corrected_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)

@app.route('/translate', methods=['GET', 'POST'])
@login_required
def translate():
    translated_text = None
    lang = "en"
    text = None

    if request.method == 'POST':
        action = request.form.get('action')
        lang = request.form.get('language')

        try:
            if action == 'translate':
                text = request.form['text']
            elif action == 'voice':
                text = spell_checker_module.voice_to_text()
            elif action == 'file_translate':
                uploaded_file = request.files['file']
                if uploaded_file.filename != '':
                    text = uploaded_file.read().decode('utf-8', errors='ignore')

            if text:
                translated = translator_module.translate(text, dest=lang)
                translated_text = translated.text
                session['last_translated'] = translated_text
                session['last_filename'] = f"translated_to_{lang}.txt"

        except Exception as e:
            print("Translation error:", e)
            return "Translation failed: " + str(e)

    return render_template('translator.html', translated_text=translated_text, lang=lang, text=text)

@app.route('/download_translation', methods=['POST'])
@login_required
def download_translation():
    text = session.get('last_translated', '')
    lang = session.get('last_filename', 'translated.txt')

    if not text:
        return redirect(url_for('translate'))

    filename = f"{lang}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)

@app.route('/library')
@login_required
def library():
    files = os.listdir(DOWNLOAD_FOLDER)
    return render_template('library.html', files=files)

@app.route('/Profile')
@login_required
def profile():
    return render_template('Profile.html')

@app.route('/delete/<filename>')
@login_required
def delete_file(filename):
    path = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(path):
        os.remove(path)
    return redirect(url_for('library'))

@app.route("/synoanto", methods=["GET", "POST"])
def synoanto():
    synonyms = []
    antonyms = []
    word = ""

    if request.method == "POST":
        word = request.form["word"]

        # Request for Synonyms
        synonym_response = requests.get(f"https://api.datamuse.com/words?rel_syn={word}")
        if synonym_response.status_code == 200:
            synonym_data = synonym_response.json()
            synonyms = [item['word'] for item in synonym_data]

        # Request for Antonyms
        antonym_response = requests.get(f"https://api.datamuse.com/words?rel_ant={word}")
        if antonym_response.status_code == 200:
            antonym_data = antonym_response.json()
            antonyms = [item['word'] for item in antonym_data]

    return render_template("synoanto.html", synonyms=synonyms, antonyms=antonyms, word=word)


@app.route("/dictionary", methods=["GET", "POST"])
def dictionary():
    definition = ""
    word = ""
    if request.method == "POST":
        word = request.form["word"]
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            try:
                definition = data[0]['meanings'][0]['definitions'][0]['definition']
            except (IndexError, KeyError):
                definition = "Definition format not recognized."
        else:
            definition = "Word not found."
    return render_template("dictionary.html", word=word, definition=definition)



if __name__ == "__main__":
    app.run(port=5001, debug=True)
