import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    rows = db.execute("SELECT symbol, SUM(no) num FROM shares WHERE holder = :userid GROUP BY symbol",
                        userid = session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE id = :userid", userid = session["user_id"])
    total = float(cash[0]['cash'])

    for row in rows:
        quote = lookup(row['symbol'])

        row["name"] = quote['name']
        row['price'] = quote['price']
        row['total'] = quote['price'] * row['num']
        total = total + row['total']

    return render_template("index.html", rows=rows, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if not symbol:
            return apology("Must write a stock's symbol")

        if not shares or int(shares) < 1:
            return apology("Number of shares to buy must be positve number")
        shares = int(shares)
        quote = lookup(request.form.get("symbol"))
        if quote==None:
            return apology("DUUUH, Wrong symbol")

        rows = db.execute("SELECT * FROM users WHERE id = :userid", userid = session["user_id"])
        diff = float("{:.2f}".format(rows[0]['cash'] - quote['price']*shares))

        if diff < 0:
            return apology("You don't have enough cash")

        #curr = db.execute("SELECT * FROM shares WHERE holder = :userid AND symbol = :symb",
        #                   userid = session["user_id"], symb = symbol)
        #if len(curr)!=0:
        #   db.execute("UPDATE shares SET price = :price, no= :no WHERE holder = :userid AND symbol = :symb",
        #              price = quote['price'], no = curr[0]['no']+shares, userid = session["user_id"], symb = symbol)

        #else:
        db.execute("INSERT INTO shares (holder, symbol, price, no, date) VALUES (:userid, :symb, :price, :no, datetime('now', 'localtime'))",
                        userid = session["user_id"], symb = symbol, price = quote['price'], no = shares)

        db.execute("UPDATE users SET cash = :cash WHERE id = :userid",
                    cash = diff, userid = session["user_id"])

        flash('Bought!')
        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    rows = db.execute("SELECT * FROM shares WHERE holder = :userid", userid = session["user_id"])
    return render_template("history.html", rows = rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        flash('Successfully logged in!')
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("Must write a stock's symbol")

        quote = lookup(request.form.get("symbol"))
        if quote==None:
            return apology("DUUUH, Wrong symbol")

        else:
            return render_template("quoted.html", name=quote['name'], price=quote['price'], symbol=quote['symbol'])

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password") or not request.form.get("confirm"):
            return apology("must provide password", 403)

        elif request.form.get("password") != request.form.get("confirm"):
            return apology("Passwords Don't Match", 403)

        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        if len(rows) != 0:
            return apology("username not available", 403)

        db.execute("INSERT INTO users(username,hash) VALUES(:username, :password) ",
                          username=request.form.get("username"), password=generate_password_hash(request.form.get("password"), method='pbkdf2:sha256', salt_length=8))

        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        if not symbol:
            return apology("Must Choose a stock's symbol")

        if not shares or int(shares) < 1:
            return apology("Number of shares to buy must be positve number")

        shares = int(shares)
        sumOfShares = db.execute("SELECT SUM(no) num FROM shares WHERE holder = :userid AND symbol= :symb",
                            userid = session['user_id'], symb = symbol)

        if len(sumOfShares) == 0 or sumOfShares[0]['num'] < shares:
            return apology("You don't have enough shares to sell")

        quote = lookup(symbol)
        cash = db.execute("SELECT cash FROM users WHERE id = :userid", userid = session['user_id'])
        newCash = float("{:.2f}".format(cash[0]['cash'] + quote['price']*shares))

        db.execute("INSERT INTO shares (holder, symbol, price, no, date) VALUES (:userid, :symb, :price, :no, datetime('now', 'localtime'))",
                        userid = session['user_id'], symb = symbol, price = quote['price'], no = (0-shares))

        db.execute("UPDATE users SET cash = :cash WHERE id = :userid",
                    cash = newCash, userid = session["user_id"])

        flash('Sold!')
        return redirect("/")

    else:
        rows = db.execute("SELECT symbol FROM shares WHERE holder = :userid GROUP BY symbol HAVING SUM(no) > 0",
                            userid = session['user_id'])
        return render_template("sell.html", rows = rows)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
