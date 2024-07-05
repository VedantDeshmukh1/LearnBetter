from flask import Flask, redirect, url_for
from config import db, rdb, auth , bucket
import os
from routes import student_routes, teacher_routes

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Register blueprints
app.register_blueprint(student_routes.bp, url_prefix='/student')
app.register_blueprint(teacher_routes.bp, url_prefix='/teacher')

@app.route('/')
def index():
    return redirect(url_for('student.home'))

if __name__ == '__main__':
    app.run(debug=True)