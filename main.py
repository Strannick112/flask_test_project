import functools
import hashlib
import os

import sqlalchemy
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///keriwell.db'
db = SQLAlchemy(app)
app.secret_key = b'My_Super_Secret_Key)'

class User(db.Model):
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    login = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    password = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    hash = sqlalchemy.Column(sqlalchemy.String, nullable=False)


class Chat(db.Model):
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    id_sender = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('user.id'))
    id_recipient = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('user.id'))

class Message(db.Model):
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    id_chat = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey(Chat.id))
    text = sqlalchemy.Column(sqlalchemy.String, nullable=False)

with app.app_context():
    db.create_all()

@app.route("/register", methods=["POST"])
def register():
    if db.session.execute(db.select(User).filter_by(login=request.form.get("login"))).first() is None:
        db.session.add(
            User(
                login=request.form.get("login"),
                password=request.form.get("password"),
                hash=hashlib.md5((request.form.get("login")+request.form.get("password")).encode()).hexdigest()
            )
        )
        db.session.commit()
        return redirect("/auth.html")
    else:
        return redirect("/register.html")

@app.route("/auth", methods=["POST"])
def auth():
    user = db.session.execute(db.select(User.login, User.hash).filter_by(login=request.form.get("login"), password=request.form.get("password"))).first()
    if user is not None:
        session["login"] = user.login
        session["hash"] = user.hash
        return redirect("/profile.html")
    else:
        return redirect("/auth.html")

def user(func):
    @functools.wraps(func)
    def decorated_func(*args, **kwargs):
        if session.get("login") is not None and session.get("hash") is not None:
            if db.session.execute(
                    db.select(User).filter_by(login=session["login"], hash=session["hash"])).first() is not None:
                return func(*args, **kwargs)
        return redirect("/auth.html")
    return decorated_func

@app.route("/profile.html", methods=["GET"])
@user
def profile():
    return render_template("profile.html")

@app.route("/logout", methods=["POST"])
@user
def logout():
    session.pop("login", None)
    session.pop("hash", None)

@app.route("/dialogs.html", methods=["GET"])
@user
def dialogs():
    user_id = db.session.execute(db.select(User.id).filter_by(login=session.get("login"))).first().id
    recipients = db.session.execute(db.select(User.login, Chat.id).join(Chat, Chat.id_sender==User.id).filter_by(id_recipient=user_id))
    senders = db.session.execute(db.select(User.login, Chat.id).join(Chat, Chat.id_recipient==User.id).filter_by(id_sender=user_id))
    users = db.session.execute(db.select(User.login))
    return render_template("/dialogs.html", recipients=recipients, senders=senders, users=users)

@app.route("/new_dialog", methods=["POST"])
@user
def new_dialog():
    if request.form.get("login") != "":
        id_recipient = db.session.execute(db.select(User.id).filter_by(login=request.form.get("login"))).first().id
        id_sender = db.session.execute(db.select(User.id).filter_by(login=session.get("login"))).first().id
        if id_recipient is not None and id_sender is not None:
            check_chat = db.session.execute(db.select(Chat).filter(
                db.or_(db.and_(Chat.id_sender==id_sender, Chat.id_recipient==id_recipient),
                db.and_(Chat.id_sender==id_recipient, Chat.id_recipient==id_sender)
               )
            )).first()
            if check_chat is None:
                count_of_chats = 0
                for _ in db.session.execute(db.select(Chat)):
                    count_of_chats += 1
                chat = Chat(id=count_of_chats+1, id_recipient=id_recipient, id_sender=id_sender)
                db.session.add(chat)
                db.session.commit()
    return redirect(url_for("dialogs"))

@app.route("/delete_dialog", methods=["GET"])
@user
def delete_dialog():
    Message.query.filter(Message.id_chat == request.args.get("chat_id")).delete()
    Chat.query.filter(Chat.id == request.args.get("chat_id")).delete()
    db.session.commit()
    return redirect(url_for("dialogs"))

@app.route("/chat.html", methods=["GET"])
@user
def chat():
    messages = db.session.execute(db.select(Message.text).join(Chat, Chat.id==Message.id_chat).filter(Message.id_chat==request.args.get("chat_id")))
    return render_template("/chat.html", messages=messages, chat_id=request.args.get("chat_id"))

@app.route("/new_message", methods=["POST"])
@user
def new_message():
    count_of_messages = 0
    for _ in db.session.execute(db.select(Message)):
        count_of_messages += 1
    message = Message(id=count_of_messages + 1, id_chat=request.form.get("chat_id"), text=request.form.get("text"))
    db.session.add(message)
    db.session.commit()
    return redirect("/chat.html?chat_id="+request.form.get("chat_id"))

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route("/<string:page>", methods=["GET"])
def others(page):
    return render_template(page)

@app.route("/", methods=["GET"])
def main():
    return render_template("index.html")

if __name__ == "__main__":
    app.run()
