from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import datetime as dt
import google.generativeai as genai
import re

class Config:
    SQLALCHEMY_DATABASE_URI = 'postgresql://cyber:3an2icE0pY11vZgaPxPucjVZIkfdfIg2@dpg-cql4ip3qf0us73brpjug-a.singapore-postgres.render.com/cybersquad'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    API_KEY = 'AIzaSyDYZbw_k1sDSg4CHgGP_1IK0iuIf8v9Ndo'

class AIModel:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    def generate_loan_advice(self, earning, loanamt, loanint, loantime):
        query = f"Give a html insertable text on step approach as on how someone earning {earning} can finish a loan having the loan amount as {loanamt} , loan interest as {loanint} and loan time as {loantime} in india and if it is not possible mention the same, please take the money to be in rupees and give code that can be used in html directly and dont mention html anywhere"
        response = self.model.generate_content(query)
        advice = response.text
        return re.sub(r'```|html', '', advice)

class Database:
    def __init__(self, app):
        self.db = SQLAlchemy(app)

    def execute_query(self, query, params=None):
        with self.db.engine.connect() as connection:
            if params:
                result = connection.execute(text(query), params)
            else:
                result = connection.execute(text(query))
            connection.commit()
            return result

class UserManager:
    def __init__(self, database):
        self.database = database

    def signin(self, email, passw):
        query = "SELECT * FROM users WHERE email = :email AND password = :pass"
        result = self.database.execute_query(query, {"email": email, "pass": passw}).fetchone()
        return result is not None

    def signup(self, name, phone, age, email, passw, usage):
        query = 'INSERT INTO users VALUES (:email, :passw, :age, :usage, :phn, NULL, :name)'
        self.database.execute_query(query, {
            "email": email, "passw": passw, "age": int(age),
            "usage": usage, "phn": int(phone), "name": name
        })

class FinanceManager:
    def __init__(self, database):
        self.database = database

    def get_balance_info(self, email):
        amountsave = self.database.execute_query("SELECT amtsave FROM users WHERE email = :email", {"email": email}).fetchone()[0]
        
        current_date = dt.date.today()
        month, year = current_date.month, current_date.year
        
        amountspent = sum(row[0] for row in self.database.execute_query(
            "SELECT amount FROM monthamt WHERE email = :email AND monthno = :month AND year = :year",
            {"email": email, "month": month, "year": year}
        ))
        
        amountearn = 0
        for row in self.database.execute_query("SELECT amount, amounttype FROM fixedexpense WHERE email = :email", {"email": email}):
            if row[1] == "outflow":
                amountspent += row[0]
            else:
                amountearn += row[0]
        
        amountleft = amountearn - amountspent
        return amountleft, amountsave, amountspent

    def add_spend(self, email, expensename, expensetype, amt):
        current_date = dt.date.today()
        month, year = current_date.month, current_date.year
        dateofadd = current_date.strftime('%Y-%m-%d')

        self.database.execute_query(
            "INSERT INTO allexpense VALUES (:email, :dateofadd, :expensename, :expensetype, :amt)",
            {"email": email, "dateofadd": dateofadd, "expensename": expensename, "expensetype": expensetype, "amt": amt}
        )

        result = self.database.execute_query(
            "SELECT amount FROM monthamt WHERE email = :email AND amounttype = :expensetype AND monthno = :month AND year = :year",
            {"email": email, "expensetype": expensetype, "month": month, "year": year}
        ).fetchone()

        if result:
            new_amount = result[0] + amt
            self.database.execute_query(
                "UPDATE monthamt SET amount = :new_amount WHERE email = :email AND amounttype = :expensetype AND year = :year AND monthno = :month",
                {"new_amount": new_amount, "email": email, "expensetype": expensetype, "year": year, "month": month}
            )
        else:
            self.database.execute_query(
                "INSERT INTO monthamt VALUES (:email, :month, :year, :expensetype, :amt)",
                {"email": email, "month": month, "year": year, "expensetype": expensetype, "amt": amt}
            )

    # Add other finance-related methods here (e.g., add_fixed, influx_list, add_influx, etc.)

class LoanManager:
    def __init__(self, database, ai_model):
        self.database = database
        self.ai_model = ai_model

    def get_loan_list(self, email):
        result = self.database.execute_query("SELECT * FROM loan WHERE email = :email", {"email": email}).fetchall()
        return [list(map(lambda x: x.rstrip() if isinstance(x, str) else x, row)) for row in result]

    def add_loan(self, email, loanname, loanamt, loanint, loantime):
        earning = self.calculate_earning(email)
        advice = self.ai_model.generate_loan_advice(earning, loanamt, loanint, loantime)
        self.database.execute_query(
            "INSERT INTO loan VALUES (:email, :loanname, :loanamt, :loanint, :loantime, :advice)",
            {"email": email, "loanname": loanname, "loanamt": loanamt, "loanint": loanint, "loantime": loantime, "advice": advice}
        )

    def calculate_earning(self, email):
        result = self.database.execute_query("SELECT amount, amounttype FROM fixedexpense WHERE email = :email", {"email": email}).fetchall()
        return sum(amount if amounttype.rstrip() == 'inflow' else -amount for amount, amounttype in result)

class FinanceApp:
    def __init__(self):
        self.app = Flask(__name__)
        self.app.config.from_object(Config)
        CORS(self.app)
        
        self.database = Database(self.app)
        self.ai_model = AIModel(Config.API_KEY)
        self.user_manager = UserManager(self.database)
        self.finance_manager = FinanceManager(self.database)
        self.loan_manager = LoanManager(self.database, self.ai_model)

        self.register_routes()

    def register_routes(self):
        @self.app.route('/signin', methods=['POST'])
        def signin():
            data = request.json
            success = self.user_manager.signin(data['email'], data['pass'])
            return jsonify({'signin': success})

        @self.app.route('/signup', methods=['POST'])
        def signup():
            data = request.json
            self.user_manager.signup(data['name'], data['phone'], data['age'], data['email'], data['pass'], data['usage'])
            return jsonify({'Message': "Success"})

        @self.app.route('/balanceinfo', methods=['POST'])
        def balance_check():
            data = request.json
            amountleft, amountsave, amountspent = self.finance_manager.get_balance_info(data['email'])
            return jsonify({
                'amountleft': amountleft,
                'amountsave': amountsave,
                'amountspent': amountspent
            })

        @self.app.route('/addspend', methods=['POST'])
        def add_spend():
            data = request.json
            self.finance_manager.add_spend(data['email'], data['expensename'], data['expensetype'], int(data['amount']))
            return jsonify({'message': 'User updated successfully'})

        # Add other routes here (e.g., addfixed, influxlist, addinflux, latestspend, bargraph, addamtsave, loanlist, addloan)

    def run(self):
        self.app.run(debug=True)

if __name__ == '__main__':
    finance_app = FinanceApp()
    finance_app.run()