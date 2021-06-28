import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

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
    # Select the user who is logged in
    cash = db.execute("SELECT cash FROM users WHERE id=:ID", ID=session.get("user_id"))
    # Select all of the stocks of this user
    purchase = db.execute("SELECT stock, stock_name, amount, price,total FROM purchase WHERE users_id=:ID", ID=session.get("user_id"))
    #Total stock value
    total = db.execute("SELECT SUM(total) AS sum FROM purchase WHERE users_id=:ID", ID=session.get("user_id"))
    grand_total =  cash[0]["cash"]
    #Loop over the rows returned by purchase query in index.html
    return render_template("index.html", PURCHASE=purchase, CASH=cash[0]["cash"], GRAND= grand_total )

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        di = lookup(request.form.get("symbol"))                             #Check symbol is correct anf not blank
        if not request.form.get("symbol") or di == None:
            return apology("Please enter the symbol or correct it")

        buy_share = request.form.get("shares")                           #Check share value entered to be positive
        if not buy_share.isdigit():
            return apology("Shares must be a positive number")

        #Check if users cash is greater than stock price
        row = db.execute("SELECT * FROM users WHERE id=:id", id=session.get("user_id"))
        cash_db = row[0]["cash"]
        price = di["price"]
        stock_name = di["name"]
        if int(buy_share) * price > int(buy_share) * cash_db:
            return apology("Not sufficient cash")

        #Store in PURCHASE table username, stock name, no of stock, price of each share, total price,
        purchase = db.execute("SELECT * FROM purchase WHERE users_id = ? AND stock = ?",session.get("user_id"), request.form.get("symbol") )
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        #If stock is not in table
        if len(purchase) == 0:
            db.execute("INSERT into purchase (users_id,username, stock, stock_name, amount, price, total, time) VALUES (?,?, ?,? , ? , ? ,?, ?)",session.get("user_id"), row[0]["username"], request.form.get("symbol") , stock_name ,buy_share , price, price*int(buy_share), timestamp)
        #If stock already exist update the amount of stocks and total value
        elif len(purchase) == 1:
            db.execute("UPDATE purchase SET amount=:amount , price=:price , total=:total WHERE users_id =:users_id AND stock = :stock", amount= float(request.form.get("shares"))+purchase[0]["amount"]  , price=price , total=(price*int(request.form.get("shares"))) +purchase[0]["total"] ,  users_id=session.get("user_id"), stock=request.form.get("symbol"))
        #Update user cash in users table
        db.execute("UPDATE  users SET cash = ? WHERE username = ? ", cash_db - (price*int(buy_share)), row[0]["username"])

        #Insert into history table
        db.execute("INSERT into history (users_id, stock,  amount, price, time) VALUES (? , ? , ? , ? , ?)",session.get("user_id"),  request.form.get("symbol") , int(request.form.get("shares")) , price, timestamp)

        # Redirect user to home page
        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    history = db.execute("SELECT stock, amount, price, time FROM history WHERE users_id=?", session.get("user_id"))
    return render_template("history.html", HISTORY=history)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
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
    return redirect("/login")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")

    if request.method == "POST":
        di = lookup(request.form.get("symbol"))
        if not di:
            return apology("Invalid stock name")
        return render_template("quoted.html", name=di["name"], price=usd(di["price"]), symbol=di["symbol"])


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        #Check if username field is empty
        if not request.form.get("username"):
            return apology("Must provide username", 400)
        #Check if password field is empty
        elif not request.form.get("password") or not request.form.get("confirmation"):
            return apology("Must provide password", 400)
        #Check if password is equal to the confirmation password
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Password must be same")

        #Check if username is already in database
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(rows) != 0:
            return apology("Username already exists", 400)
        else:
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", request.form.get("username"), generate_password_hash(request.form.get("password")))
            return redirect("/login")
    else:
        return render_template("register.html")





@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":

        # Get stock from purchase table by using user id
        stock_db = db.execute("SELECT stock FROM purchase WHERE users_id = ?", session.get("user_id"))
        #Loop over the stock_db and append to list
        li = []
        for stock in stock_db:
            if  stock not in li:
                li.append(stock)
        return render_template("sell.html", LIST=li)

    if request.method == "POST":


        #Get symbol
        di = lookup(request.form.get("symbol"))
        price=di["price"]
        shares=int(request.form.get("shares"))

        #update users table
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session.get("user_id"))
        db.execute("UPDATE  users SET cash = ? WHERE id = ? ", cash[0]["cash"] +  di["price"]*int(request.form.get("shares")), session.get("user_id"))

        #If user is selling more shares than she owns apologize
        sum_amount = db.execute("SELECT SUM(amount) AS total FROM purchase WHERE users_id = ? GROUP BY stock HAVING stock = ?", session.get("user_id"), request.form.get("symbol"))
        if sum_amount[0]["total"] < int(request.form.get("shares")):
            return apology("You do not have enough stocks")
        #Update the amount,price and total in purchase table
        purchase=db.execute("SELECT * FROM purchase WHERE users_id=:users_id AND stock=:stock", users_id=session.get("user_id"), stock=request.form.get("symbol"))
        # If user is selling some of the shares
        db.execute("UPDATE purchase SET amount=:amount , price=:price , total=:total WHERE users_id =:users_id AND stock = :stock", amount= purchase[0]["amount"]-int(request.form.get("shares"))  , price=price , total=purchase[0]["total"]-(price*int(request.form.get("shares")))  ,  users_id=session.get("user_id"), stock=request.form.get("symbol"))
        # Check if user is selling all of the shares
        if int(request.form.get("shares")) == purchase[0]["amount"]:
            db.execute("DELETE FROM purchase WHERE users_id=:users_id AND stock=:stock", users_id=session.get("user_id"), stock=request.form.get("symbol") )

        # Insert into history table
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.execute("INSERT into history (users_id, stock,  amount, price, time) VALUES (? , ? , ? , ? , ?)",session.get("user_id"),  request.form.get("symbol") , -int(request.form.get("shares")) , price, timestamp)
        return redirect("/")



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
