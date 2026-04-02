import bcrypt
from flask import Flask, render_template, request, redirect, url_for, session, flash
import pickle
import string
import mysql.connector
import re
import nltk

from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords
nltk.download('stopwords')
nltk.download('wordnet')

app = Flask(__name__)
app.secret_key = '1c8073775dbc85a92ce20ebd44fd6a4fd832078f59ef16ec'

app.jinja_env.globals.update(enumerate=enumerate)

wnl = WordNetLemmatizer()

tfidf = pickle.load(open('vectorizer.pkl', 'rb'))
model = pickle.load(open('model.pkl', 'rb'))


def transform_text(sms):
    message = re.sub(pattern='[^a-zA-Z]', repl=' ', string=sms)
    message = message.lower()
    words = message.split()
    filtered_words = [word for word in words if word not in set(stopwords.words('english'))]
    lemm_words = [wnl.lemmatize(word) for word in filtered_words]
    return ' '.join(lemm_words)


# Database connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="JD50188@MYSQL",
    database="smc"
)


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/index')
def index():
    if 'user' in session:
        return render_template('index.html')
    else:
        return redirect(url_for('signin'))


@app.route('/predict', methods=['POST'])
def predict():
    input_sms = request.form.get('message')
    transformed_sms = transform_text(input_sms)
    vector_input = tfidf.transform([transformed_sms])
    result = model.predict(vector_input)[0]

    prediction = "Spam" if result == 1 else "Not Spam"

    # Save history
    if 'user' in session:
        user_id = session['user'][0]
        cur = db.cursor()
        cur.execute(
            "INSERT INTO search_history (user_id, message, prediction) VALUES (%s, %s, %s)",
            (user_id, input_sms, prediction)
        )
        db.commit()
        cur.close()

    return render_template('result.html', prediction=prediction)


@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('signin'))

    user_id = session['user'][0]
    cur = db.cursor()
    cur.execute(
        "SELECT id, message, prediction, searched_at FROM search_history WHERE user_id = %s ORDER BY searched_at DESC",
        (user_id,)
    )
    history = cur.fetchall()
    cur.close()

    return render_template('dashboard.html', history=history, user=session['user'])


@app.route('/delete_history/<int:history_id>', methods=['POST'])
def delete_history(history_id):
    if 'user' not in session:
        return redirect(url_for('signin'))

    user_id = session['user'][0]

    cur = db.cursor()
    cur.execute(
        "DELETE FROM search_history WHERE id = %s AND user_id = %s",
        (history_id, user_id)
    )
    db.commit()
    cur.close()

    return redirect(url_for('dashboard'))


@app.route('/signin')
def signin():
    if 'user' in session:
        return redirect(url_for('index'))
    return render_template('signin.html')


@app.route('/signup', methods=['GET'])
def signup():
    return render_template('signup.html')


# 🔐 REGISTER (HASH PASSWORD HERE)
@app.route('/register', methods=['POST'])
def register():
    full_name = request.form['full_name'].strip()
    username = request.form['username'].strip()
    email = request.form['email'].strip().lower()
    phone = request.form['phone'].strip()
    password = request.form['password'].strip()
    confirm_password = request.form['confirm_password']

    if password != confirm_password:
        return "Password and Confirm Password do not match."

    # HASH PASSWORD
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

    cur = db.cursor()
    cur.execute(
        "INSERT INTO users (full_name, username, email, phone, password) VALUES (%s, %s, %s, %s, %s)",
        (full_name, username, email, phone, hashed_password.decode())
    )
    db.commit()
    cur.close()

    flash('Registration successful', 'success')
    return redirect('/signin')


# 🔐 LOGIN (CHECK HASH HERE)
@app.route('/login', methods=['POST'])
def login():
    email = request.form['email'].strip().lower()
    password = request.form['password'].strip()
    remember_me = request.form.get('remember_me')

    cur = db.cursor()
    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cur.fetchone()
    cur.close()

    if user:
        stored_password = user[5]

        # CHECK HASH
        if bcrypt.checkpw(password.encode(), stored_password.encode()):
            session['user'] = user

            if remember_me:
                session.permanent = True

            return redirect(url_for('index'))
        else:
            return "Wrong password"
    else:
        return "User not found"


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)