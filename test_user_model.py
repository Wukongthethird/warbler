"""User model tests."""

# run these tests like:
#
#    python -m unittest test_user_model.py


from app import app,  CURR_USER_KEY
import os
from unittest import TestCase
from sqlalchemy.exc import IntegrityError

from models import db, User, Message, Follows

# BEFORE we import our app, let's set an environmental variable
# to use a different database for tests (we need to do this
# before we import our app, since that will have already
# connected to the database

os.environ['DATABASE_URL'] = "postgresql:///warbler-test"
PASSWORD = "HASHED_PASSWORD"

# Now we can import app


# Create our tables (we do this here, so we only create the tables
# once for all tests --- in each test, we'll delete the data
# and create fresh new clean test data

db.create_all()

class UserModelTestCase(TestCase):
    """Test views for messages."""

    def setUp(self):
        """Create test client, add sample data."""

        User.query.delete()
        Message.query.delete()
        Follows.query.delete()

        u = User.signup(
            email="test@test.com",
            username="testuser",
            password="HASHED_PASSWORD",
            image_url=None
        )

        db.session.add(u)
        db.session.commit()

        self.client = app.test_client()
        self.test_user1 = u

    def tearDown(self):
        """Clean up any fouled transaction."""

        db.session.rollback()

    def test_user_model(self):
        """Does basic model work?"""

        # User should have no messages & no followers
        self.assertEqual(len(self.test_user1.messages), 0)
        self.assertEqual(len(self.test_user1.followers), 0)

    def test_repr(self):
        """Does the repr method work?"""

        # User should have no messages & no followers
        self.assertEqual(repr(
            self.test_user1), f"<User #{self.test_user1.id}: {self.test_user1.username}, {self.test_user1.email}>")

    def test_follow(self):
        """Is follow keeping track of the right users."""
        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.test_user1.id

            user2 = User(username="testuser2",
                         email="test2@test.com",
                         password="testuser2"
                         )

            db.session.add(user2)
            db.session.commit()

            user3 = User(username="testuser3",
                         email="test3@test.com",
                         password="testuser3"
                         )

            db.session.add(user3)
            db.session.commit()

            resp = c.post(f"/users/follow/{user2.id}")

        # Make sure it redirects

            test_follow = Follows.query.filter_by(
                user_following_id=self.test_user1.id).one()

            self.assertEqual(resp.status_code, 302)
            self.assertEqual(user2.id, test_follow.user_being_followed_id)
            self.assertEqual(self.test_user1.id,
                             test_follow.user_following_id)

            self.assertNotEqual(user3.id, test_follow.user_being_followed_id)
            self.assertNotEqual(user3.id, test_follow.user_following_id)
    
    def test_user_signup(self):
        """Successfully create a new user given valid credentials?"""

        user = User.signup(username="testuser2",
                         email="test2@test.com",
                         password="testuser2",
                         image_url = None)

        db.session.add(user)
        db.session.commit()

        users = User.query.all()

        self.assertEqual(len(users),2)

        # signup(cls, username, email, password, image_url)

    def test_user_invalid_signup(self):
        """Test if invalid credentials fail to create a new user"""

        with self.client as c:
            resp = c.post('/signup', data={"username":"testuser",
                            "email":"test2@test.com",
                            "password":"testuser2"
                            })

            html = resp.get_data(as_text=True)
            
            users = User.query.all()
            self.assertEqual(len(users),1)
            self.assertIn('<li><a href="/signup">Sign up</a></li>', html)

    def test_authentication(self):
        """Test if valid user can be authenticated"""

        user = User.authenticate(self.test_user1.username, PASSWORD)
        self.assertEqual(self.test_user1, user)

        user = User.authenticate(self.test_user1.username, "wrong_password")
        self.assertIs(user, False)

        user = User.authenticate("wrong_username", PASSWORD)
        self.assertIs(user, False)


        

    
    
