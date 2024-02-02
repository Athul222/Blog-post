from flask import Flask, render_template, request
import requests
import smtplib
from dotenv import dotenv_values

config = {
    **dotenv_values("./Backend/day-60/upgraded-blog/.env.secret")
}

MY_EMAIL = config["EMAIL_ID"]
PASSWORD = config["PASSWORD"]
TO_MAIL = config["TO_MAIL"]

# USE YOUR OWN npoint LINK! ADD AN IMAGE URL FOR YOUR POST. 👇
posts = requests.get("https://api.npoint.io/c790b4d5cab58020d391").json()

app = Flask(__name__)


@app.route('/')
def get_all_posts():
    return render_template("index.html", all_posts=posts)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/contact", methods=['GET', 'POST'])
def receive_data():
    if request.method == "POST":
        name= request.form["name"]
        email= request.form["email"]
        phone_number= request.form["phone"]
        message= request.form["message"]
        
        send_mail(name=name, email=email, number=phone_number, message=message)
        
        return render_template("contact.html", msg_sent=True)
    return render_template("contact.html", msg_sent=False)

def send_mail(name, email, number, message):
    with smtplib.SMTP("smtp.gmail.com") as connection:
            connection.starttls()
            connection.login(user=MY_EMAIL, password=PASSWORD)
            connection.sendmail(
                from_addr=MY_EMAIL,
                to_addrs=TO_MAIL,
                msg=f"Subject:New Message\n\nName: {name}\nEmail: {email}\n Phone Number: {number}\n Message: {message}" 
            )

@app.route("/post/<int:index>")
def show_post(index):
    requested_post = None
    for blog_post in posts:
        if blog_post["id"] == index:
            requested_post = blog_post
    return render_template("post.html", post=requested_post)

if __name__ == "__main__":
    app.run(debug=True, port=5001)
