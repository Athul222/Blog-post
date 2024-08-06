import os
import smtplib
from datetime import date
from dotenv import dotenv_values
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm

CURRENT_YEAR=date.today().strftime("%Y") 

# create flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI", "sqlite:///posts.db")
db = SQLAlchemy(model_class=Base)
db.init_app(app)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
        
    #This will act like a List of BlogPost objects attached to each User. 
    #The "author" refers to the author property in the BlogPost class.
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")
    
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
        
    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    # Create reference to the User object. The "posts" refers to the posts property in the User class.
    author = relationship("User", back_populates="posts")
    
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    
    comments = relationship("Comment", back_populates="parent_posts")
        
class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    post_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("blog_posts.id"))
    parent_posts = relationship("BlogPost", back_populates="comments")

with app.app_context():
    db.create_all()
    

# Create a user loader callback
@login_manager.user_loader
def load_user(user_id):
    return db.session.execute(db.select(User).where(User.id == user_id)).scalar()


# Create an admin-only decorator
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # try-catch to handle, if the user enters the endpoint that's only accessible to admin before login/registering
        try:
            # If id is not 1 then return abort with 403 error
            if current_user.id != 1:
                return abort(403)
        except AttributeError:
            return redirect(url_for("login"))
        # Otherwise continue with the route function
        return f(*args, **kwargs)

    return decorated_function


# Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    salt_round = 10
    if request.method == "POST":
        
        email = request.form.get("email")
        
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        if user:
            flash("You've already signed up with that email, login instead")
            return redirect(url_for("login"))
        
        hash_and_salted_password = generate_password_hash(
            request.form.get("password"), 
            method="pbkdf2:sha256", 
            salt_length= salt_round
        )
        new_user = User(
            email= email,
            password= hash_and_salted_password,
            name= request.form.get("name")
        )
        
        # adding the data to the database + commit
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        
        return redirect(url_for("get_all_posts"))
    
    return render_template("register.html", form=form, logged_in=current_user.is_authenticated, year=CURRENT_YEAR)


# Retrieve a user from the database based on their email. 
@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if request.method == "POST":
        user_entered_email = request.form.get("email")
        user_entered_password = request.form.get("password")
        
        user = db.session.execute(db.select(User).where(User.email == user_entered_email)).scalar()
        # if user(email) already exists 
        # compare email -> email doesn't exist then render to register
        if user:
            hashed_password = user.password
            compared_password = check_password_hash(hashed_password, user_entered_password) 
            # compare password -> if wrong then flash a incorrect password message 
            if compared_password:
                login_user(user)
                return redirect(url_for("get_all_posts"))
            flash("Incorrect password")
            return redirect(url_for("login"))
            
        flash("Entered email doesn't exists, Try again or register a new account")
        return redirect(url_for("login"))
        
    return render_template("login.html", form=form, logged_in=current_user.is_authenticated, year=CURRENT_YEAR)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts, logged_in=current_user.is_authenticated, current_user=current_user, year=CURRENT_YEAR)


# Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    comment_form = CommentForm()
    gravatar = Gravatar(app,
                    size=100,
                    rating='x',
                    default='retro',
                    force_default=False,
                    use_ssl=False,
                    base_url=None)
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))
        
        comment_text = request.form.get("comment_text")
        new_comment = Comment(
            author_id=current_user.id,
            text=comment_text,
            post_id=post_id
            )
        db.session.add(new_comment)
        db.session.commit()
        comment_form.comment_text.data = ""
        
    return render_template("post.html", post=requested_post, form=comment_form, logged_in=current_user.is_authenticated, year=CURRENT_YEAR)


# Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y") 
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, current_user=current_user, year=CURRENT_YEAR)


# Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, current_user=current_user, year=CURRENT_YEAR)


# Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html", year=CURRENT_YEAR)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        data = request.form
        send_mail(name=data["name"], email=data["email"], phone=data["phone"], message=data["message"])
        return render_template("contact.html", msg_sent=True, year=CURRENT_YEAR)
    return render_template("contact.html", msg_sent=False, year=CURRENT_YEAR)

# send mail logic
def send_mail(name, email, phone, message):
    email_message = f"Subject:New Message\n\nName: {name}\nEmail: {email}\nPhone: {phone}\nMessage: {message}"
    with smtplib.SMTP("smtp.gmail.com") as connection:
        connection.starttls()
        connection.login(user=os.environ.get("EMAIL"), password=os.environ.get("PASSWORD"))
        connection.sendmail(
            from_addr=os.environ.get("EMAIL"),
            to_addrs=os.environ.get("EMAIL"),
            msg=email_message
        )

if __name__ == "__main__":
    app.run(debug=True)
