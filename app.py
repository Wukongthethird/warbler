from models import db, connect_db, User, Message, Like
from forms import UserAddForm, LoginForm, MessageForm, EditUserForm
import os

from flask import Flask, render_template, request, flash, redirect, session, g, jsonify, abort
from flask_debugtoolbar import DebugToolbarExtension
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from flask_cors import CORS, cross_origin

CURR_USER_KEY = "curr_user"

database_url = os.environ.get('DATABASE_URL', 'postgresql:///warbler')

database_url = database_url.replace('postgres://', 'postgresql://')
app = Flask(__name__)
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

# Get DB_URI from environ variable (useful for production/testing) or,
# if not set there, use development local db.
app.config['SQLALCHEMY_DATABASE_URI'] = database_url

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = False
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'shh')
toolbar = DebugToolbarExtension(app)

connect_db(app)


##############################################################################
# User signup/login/logout


@app.before_request
def add_user_to_g():
    """If we're logged in, add curr user to Flask global."""

    if CURR_USER_KEY in session:
        g.user = User.query.get(session[CURR_USER_KEY])

    else:
        g.user = None


def do_login(user):
    """Log in user."""

    session[CURR_USER_KEY] = user.id


def do_logout():
    """Logout user."""

    if CURR_USER_KEY in session:
        del session[CURR_USER_KEY]


@app.route('/signup', methods=["GET", "POST"])
def signup():
    """Handle user signup.

    Create new user and add to DB. Redirect to home page.

    If form not valid, present form.

    If the there already is a user with that username: flash message
    and re-present form.
    """

    form = UserAddForm()

    if form.validate_on_submit():
        try:
            user = User.signup(
                username=form.username.data,
                password=form.password.data,
                email=form.email.data,
                image_url=form.image_url.data or User.image_url.default.arg,
            )
            db.session.commit()

        except IntegrityError:
            flash("Username already taken", 'danger')
            return render_template('users/signup.html', form=form)

        do_login(user)

        return redirect("/")

    else:
        return render_template('users/signup.html', form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    """Handle user login."""

    form = LoginForm()

    if form.validate_on_submit():
        user = User.authenticate(form.username.data,
                                 form.password.data)

        if user:
            do_login(user)
            flash(f"Hello, {user.username}!", "success")
            return redirect("/")

        flash("Invalid credentials.", 'danger')

    return render_template('users/login.html', form=form)


@app.route('/logout')
def logout():
    """Handle logout of user."""

    # IMPLEMENT THIS
    do_logout()

    flash("You've Successfully Logged out")
    return redirect("/")


##############################################################################
# General user routes:

@app.route('/users')
def list_users():
    """Page with listing of users.

    Can take a 'q' param in querystring to search by that username.
    """

    search = request.args.get('q')

    if not search:
        users = User.query.all()
    else:
        users = User.query.filter(User.username.like(f"%{search}%")).all()

    return render_template('users/index.html', users=users)


@app.route('/users/<int:user_id>')
def users_show(user_id):
    """Show user profile."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)

    return render_template('users/show.html', user=user)


@app.route('/users/<int:user_id>/following')
def show_following(user_id):
    """Show list of people this user is following."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template('users/following.html', user=user)


@app.route('/users/<int:user_id>/followers')
def users_followers(user_id):
    """Show list of followers of this user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template('users/followers.html', user=user)


@app.route('/users/follow/<int:follow_id>', methods=['POST'])
def add_follow(follow_id):
    """Add a follow for the currently-logged-in user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followed_user = User.query.get_or_404(follow_id)
    g.user.following.append(followed_user)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")


@app.route('/users/stop-following/<int:follow_id>', methods=['POST'])
def stop_following(follow_id):
    """Have currently-logged-in-user stop following this user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followed_user = User.query.get(follow_id)
    g.user.following.remove(followed_user)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")


@app.route('/users/profile', methods=["GET", "POST"])
def profile():
    """Update profile for current user."""
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = g.user
    form = EditUserForm(obj=user)

    if form.validate_on_submit():
        try:
            user.username = form.username.data
            password = form.password.data
            user.email = form.email.data
            user.image_url = form.image_url.data or User.image_url.default.arg
            user.bio = form.bio.data
            user.header_image_url = form.header_image_url.data or User.header_image_url.default.arg

            if User.authenticate(user.username, password):
                db.session.commit()
                return redirect(f'/users/{user.id}')
            else:
                flash("Invalid credentials.", 'danger')
                return redirect('/')

        except IntegrityError:
            flash("Username already taken", 'danger')
            return render_template('users/edit.html', form=form)

    return render_template('/users/edit.html', form=form, user_id=user.id)


@app.route('/users/delete', methods=["POST"])
def delete_user():
    """Delete user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    do_logout()

    db.session.delete(g.user)
    db.session.commit()

    return redirect("/signup")


##############################################################################
# Messages routes:

@app.route('/messages/new', methods=["GET", "POST"])
def messages_add():
    """Add a message:

    Show form if GET. If valid, update message and redirect to user page.
    """

    if not g.user:

        flash("Access unauthorized.", "danger")
        return redirect("/")

    form = MessageForm()

    if form.validate_on_submit():
        msg = Message(text=form.text.data)
        # if msg.user_id != g.user.id:
        #     flash("Access unauthorized.", "danger")
        #     return redirect("/")

        g.user.messages.append(msg)
        db.session.commit()

        return redirect(f"/users/{g.user.id}")

    return render_template('messages/new.html', form=form)


@app.route('/messages/<int:message_id>', methods=["GET"])
def messages_show(message_id):
    """Show a message."""

    msg = Message.query.get(message_id)
    return render_template('messages/show.html', message=msg)


@app.route('/messages/<int:message_id>/delete', methods=["POST"])
def messages_destroy(message_id):
    """Delete a message."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    msg = Message.query.get(message_id)
    if msg.user_id != g.user.id:
        flash("Access unauthorized.", "danger")
        return redirect("/")
    db.session.delete(msg)
    db.session.commit()

    return redirect(f"/users/{g.user.id}")

##############################################################################
# Like routes:


# @app.route('/like/<int:message_id>', methods=['POST'])
# @cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
@app.route('/messages/<int:message_id>/like', methods=['POST'])
def add_like(message_id):
    """Allows user to like a message"""
    # user = g.user
    # print('user', user)
    # if not g.user:
    #     flash("Sign in to like.")
    #     return redirect("/")

    # liked_message = Message.query.get_or_404(message_id)
    # g.user.liked_messages.append(liked_message)
    # db.session.commit()
    #  json
    print('here')
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    liked_message = Message.query.get_or_404(message_id)
    if liked_message.user_id == g.user.id:
        return abort(403)

    if liked_message in g.user.liked_messages:
        g.user.liked_messages.remove(liked_message)
    else:
        g.user.liked_messages.append(liked_message)

    db.session.commit()

    return redirect("/")

    # return jsonify(result="like")


@app.route('/like/stop-liking/<int:message_id>', methods=['POST'])
def remove_like(message_id):
    """Allows user to remove a like on a message"""

    if not g.user:
        flash("Access unauthorized.")
        return redirect("/")

    liked_message = Message.query.get_or_404(message_id)
    g.user.liked_messages.remove(liked_message)
    db.session.commit()

    return jsonify(result="dislike")


@app.route('/users/<int:user_id>/likes', methods=["GET"])
def show_likes(user_id):
    """Shows all liked messages"""

    if not g.user:
        flash("Sign in to like.")
        return redirect("/")

    # user = g.user
    user = User.query.get_or_404(user_id)
    return render_template('/likes/show.html', user=user)

##############################################################################
# Homepage and error pages


@app.route('/')
def homepage():
    """Show homepage:

    - anon users: no messages
    - logged in: 100 most recent messages of followed_users
    """

    if g.user:
        follower_ids = [user.id for user in g.user.followers]
        messages = (Message
                    .query
                    .filter(or_(Message.user_id == g.user.id, Message.user_id.in_(follower_ids)))
                    .order_by(Message.timestamp.desc())
                    .limit(100)
                    .all())

        return render_template('home.html', messages=messages)

    else:
        return render_template('home-anon.html')


##############################################################################
# Turn off all caching in Flask
#   (useful for dev; in production, this kind of stuff is typically
#   handled elsewhere)
#
# https://stackoverflow.com/questions/34066804/disabling-caching-in-flask

@app.after_request
def add_header(response):
    """Add non-caching headers on every request."""

    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control
    response.cache_control.no_store = True
    return response
