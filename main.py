import os
import re
import random
import hashlib
import hmac
import time
from string import letters

import jinja2
import webapp2

from user import User

from google.appengine.ext import db

# POKEMON GO BLOG

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)

secret = 'gobucs'

def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)

def make_secure_val(val):
        return "%s|%s" % (val, hmac.new(secret, val).hexdigest())

def check_secure_val(secure_val):
    val = secure_val.split('|')[0]
    if secure_val == make_secure_val(val):
        return val


class BlogHandler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        params["user"] = self.user
        return render_str(template, **params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    def set_secure_cookie(self, name, val):
        cookie_val = make_secure_val(val)
        self.response.headers.add_header(
            'Set-Cookie',
            '%s=%s; Path=/' % (name, cookie_val)) #Set cookies

    def read_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        return cookie_val and check_secure_val(cookie_val)

    def login(self, user):
        self.set_secure_cookie('user_id', str(user.key().id()))

    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

    def initialize(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)
        uid = self.read_secure_cookie("user_id")
        self.user = uid and User.by_id(int(uid))
def render_post(response, post):
    response.out.write("<b>" + post.subject + "</b><br>")
    response.out.write(post.content)

class MainPage(BlogHandler):
  def get(self):
        if self.user:
            self.render("front.html")
        else:
            self.redirect("/login")
# User.py went here previously. 

# Posting new content

def blog_key(name= "default"):
    return db.Key.from_path("blogs", name)

class Post(db.Model):
    subject = db.StringProperty(required = True)
    content = db.TextProperty(required = True)
    created = db.DateTimeProperty(auto_now_add = True)
    last_modified = db.DateTimeProperty(auto_now=True)
    author = db.StringProperty(required = True)
    likes = db.IntegerProperty(required = True)
    dislikes = db.IntegerProperty(required = True)
    liked_by = db.ListProperty(str)
    disliked_by = db.ListProperty(str)
    
    def render(self):
        self._render_text = self.content.replace("\n", "<br>")
        return render_str("post.html", p = self)

    @property
    def comments(self):
        return Comment.all().filter("post = ", str(self.key().id()))

class BlogFront(BlogHandler): # search query for the order the blog should display its entries. 
    def get(self):
        # posts = Post.all().order("-created")
        posts = db.GqlQuery("select * from Post order by created desc limit 10")
        self.render("front.html", posts = posts)

class PostPage(BlogHandler): # Post the blog entries.  
    def get(self, post_id):
        key = db.Key.from_path('Post', int(post_id), parent=blog_key())
        post = db.get(key)

        if not post:
            self.error(404)
            return

        self.render("permalink.html", post = post)

class NewPost(BlogHandler): # New Posts for the blog
    def get(self):
        if self.user:
            self.render("newpost.html")
        else:
            self.redirect("/login")

    def post(self):
        if not self.user:
            return 
        self.redirect('/blog')
        subject = self.request.get('subject')
        content = self.request.get('content')
        author = self.request.get("author")

        if subject and content:
            p = Post(parent = blog_key(), subject = subject, content = content, author=author, likes= 0, dislikes=0, liked_by=[], disliked_by=[])
            p.put() #store content into database
            self.redirect("/blog/%s" % str(p.key().id()))
        else:
            error = "Please fill in the subject and content"
            self.render("newpost.html", subject=subject, content=content, error=error)

class EditPost(BlogHandler): # Edit your post
	def get(self):
 		if self.user:
 			post_id = self.request.get('post')
 			key = db.Key.from_path('Post', int(post_id), parent=blog_key())
 			post = db.get(key)
 			# author = post.author
			# loggedUser = self.user.name
			if not post:
				self.error(404)
				return
			self.render("editpost.html", subject = post.subject, content =post.content)
		else:
			self.redirect("/login")
	
	def post(self):
		if self.user:
			post_id = self.request.get('post')
			key = db.Key.from_path('Post', int(post_id), parent=blog_key())
			post = db.get(key)
			subject = self.request.get('subject')
			content = self.request.get('content')
			if subject and content:
					post.subect = subject
					post.content = content
					post.put()
					self.redirect("/blog/%s" % str(post.key().id()))
			else:
				error = "Please fill in both a subject and content."
				self.render("editpost.html", subject = subject, content = content, error='error')
		else:
			self.redirect("/login")

class DeletePost(BlogHandler): # Delete your post
    def get(self):
        if self.user:
            post_id = self.request.get("post")
            key = db.Key.from_path("Post", int(post_id), parent=blog_key())
            post = db.get(key)
            if not post:
                self.error(404)
                return 
            self.render("deletepost.html", post = post)
        else:
            self.redirect("/login")

    def post(self):
        post_id = self.request.get("post")
        key = db.Key.from_path("Post", int(post_id), parent=blog_key())
        post = db.get(key)
        # if post and post.author.username == self.user.username:
        post.delete()
        self.render("deletesuccess.html")

class Comment(db.Model):
	comment = db.StringProperty(required=True)
	post = db.StringProperty(required=True)
	author = db.StringProperty(required=True)

	@classmethod
	def render(self):
		self.render("comment.html")
class NewComment(BlogHandler):
	def get(self):

		if not self.user:
			self.redirect("/login")
			return 
		post_id = self.request.get("post")
		post = Post.get_by_id(int(post_id), parent=blog_key())
		subject = post.subject
		content = post.content
		self.render("newcomment.html", subject=subject, content=content, pkey=post.key())

	def post(self):
		post_id = self.request.get("post")
		key = db.Key.from_path("Post", int(post_id), parent=blog_key())
		post = db.get(key)
		if not post:
			self.error(404)
			return
		if not self.user:
			self.redirect("login")
			return
		comment = self.request.get("comment")

		if comment:
			author = self.request.get("author") # check how author was defined
			c = Comment(comment=comment, post=post_id, parent=self.user.key(), author=author)
			c.put()
			self.redirect("/blog/%s" % str(post_id))
			
		else:
			error = "please comment"
			self.render("permalink.html", post=post, content=content, error=error)

class EditComment(BlogHandler):
	def get(self, post_id, comment_id):
		if self.user:
			post = Post.get_by_id(int(post_id), parent=blog_key())
			comment = Comment.get_by_id(int(comment_id), parent=self.user.key())	
			if comment:
				self.render("editcomment.html", subject=post.subject, content=post.content, comment=comment.comment)
			else:
				self.redirect("/commenterror")
		else:
			self.redirect("/login")
		

	def post(self, post_id, comment_id):
		comment=Comment.get_by_id(int(comment_id), parent=self.user.key())
		if comment.parent().key().id() == self.user.key().id():
			comment_temp = self.request.get("comment")
			if comment_temp:
				comment.comment =comment_temp
				comment.put()
				self.redirect("/blog/%s" % str(post_id)) # TODO: Should show an updated comment
			else:
				error = "Please fill in comment."
				self.render("editcomment.html", subject=post.subject, content=post.content, comment=comment.comment)
		else:
			self.redirect("/login")

class DeleteComment(BlogHandler):
	def post(self, post_id, comment_id):
		comment = Comment.get_by_id(int(comment_id), parent=self.user.key())
		if comment:
			comment.delete()
			self.redirect("/blog/%s" % str(post_id))
		else:
			self.write("Sorry, something went wrong..")

class LikePost(BlogHandler): # likes funtion
    def get(self, post_id):
        if not self.user:
            self.redirect("/login")
        else:
            key = db.Key.from_path("Post", int(post_id), parent=blog_key())
            post = db.get(key)
            author = post.author
            logged_user = self.user.name

            if author == logged_user or logged_user in post.liked_by:
                self.render("liked.html")
            else:
                post.likes +=1
                post.liked_by.append(logged_user)
                post.put()
                self.redirect("/blog")

class DislikePost(BlogHandler): # dislikes funtion
    def get(self, post_id):
       if not self.user:
           self.redirect("/login")
       else:
           key = db.Key.from_path("Post", int(post_id), parent=blog_key())
           post = db.get(key)
           author = post.author
           logged_user = self.user.name

           if author == logged_user or logged_user in post.disliked_by:
               self.render("disliked.html")
           else:
                post.dislikes +=1
                post.disliked_by.append(logged_user)
                post.put()
                self.redirect("/blog")

# Sign Up!
USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
def valid_username(username):
    return username and USER_RE.match(username)

PASS_RE = re.compile(r"^.{3,20}$")
def valid_password(password):
    return password and PASS_RE.match(password)

EMAIL_RE  = re.compile(r'^[\S]+@[\S]+\.[\S]+$')
def valid_email(email):
    return not email or EMAIL_RE.match(email)

class Signup(BlogHandler):

    def get(self):
        self.render("signup-form.html")

    def post(self):
        have_error = False
        self.username = self.request.get('username')
        self.password = self.request.get('password')
        self.verify = self.request.get('verify')
        self.email = self.request.get('email')

        params = dict(username = self.username,
                      email = self.email)

        if not valid_username(self.username):
            params['error_username'] = "That's not a valid username."
            have_error = True

        if not valid_password(self.password):
            params['error_password'] = "That wasn't a valid password."
            have_error = True
        elif self.password != self.verify:
            params['error_verify'] = "Your passwords didn't match."
            have_error = True

        if not valid_email(self.email):
            params['error_email'] = "That's not a valid email."
            have_error = True

        if have_error:
            self.render('signup-form.html', **params)
        else:
            self.done()

    def done(self, *a, **kw):
        raise NotImplementedError

class TrainerSignup(Signup):
    def done(self):
        self.redirect('/trainer/welcome?username=' + self.username)

class Register(Signup):
    def done(self):
# make sure the user doesn't already exist
        u = User.by_name(self.username)
        if u:
            msg = 'That user already exists.'
            self.render('signup-form.html', error_username = msg)
        else:
            u = User.register(self.username, self.password, self.email)
            u.put()

            self.login(u)
            self.redirect('/blog')
class Login(BlogHandler):
    def get(self):
        self.render('login-form.html')

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')

        u = User.login(username, password)
        if u:
            self.login(u)
            self.redirect('/blog')
        else:
            msg = 'Invalid login'
            self.render('login-form.html', error = msg)
# Logout and redirect to main page
class Logout(BlogHandler):
    def get(self):
        self.logout()
        self.redirect('/blog')

class Unit3Welcome(BlogHandler):
    def get(self):
        if self.user:
            self.render('welcome.html', username = self.user.name)
        else:
            self.redirect('/signup')

class Welcome(BlogHandler):
    def get(self):
        username = self.request.get('username')
        if valid_username(username):
            self.render('welcome.html', username = username)
        else:
            self.redirect('/trainer/signup')

app = webapp2.WSGIApplication([('/', MainPage),
                               ('/trainer/signup', TrainerSignup),
                               ('/trainer/welcome', Welcome),
                               ('/blog/?', BlogFront),
                               ('/blog/([0-9]+)', PostPage),
                               ('/blog/newpost', NewPost),
                               ("/blog/editpost", EditPost),
                               ("/blog/delete", DeletePost),
                               ("/blog/([0-9]+)/like", LikePost),
                               ("/blog/([0-9]+)/dislike", DislikePost),
                               ('/signup', Register),
                               ('/login', Login),
                               ('/logout', Logout), 
                               ("/blog/newcomment", NewComment),
                               ("/blog/([0-9]+)/editcomment/([0-9]+)", EditComment),
                               ("/blog/([0-9]+)/deletecomment/([0-9]+)", DeleteComment),
                               ('/unit3/welcome', Unit3Welcome),
                               ],
                              debug=True)
