from flask import Flask , request ,render_template
from flask_mail import Mail, Message

app = Flask(__name__)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587 
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'learnbetter310@gmail.com'
app.config['MAIL_PASSWORD'] = 'projectearnmoney'

mail = Mail(app)

@app.route('/send_email', methods=['GET', 'POST'])
def send_email():
    if request.method == 'POST':
        recipient = request.form['recipient']
        subject = request.form['subject']
        body = request.form['body']

        msg = Message(subject, sender='learnbetter310@gmail.com', recipients=[recipient])
        msg.body = body

        try:
            mail.send(msg)
            return "Email sent!"
        except Exception as e:
            return f"Error sending email: {str(e)}"

    return render_template('send_email.html')
if __name__ == '__main__':
    app.run(debug=True)