from flask import Flask, request,jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import datetime as dt
import google.generativeai as genai
import re

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://cyber:3an2icE0pY11vZgaPxPucjVZIkfdfIg2@dpg-cql4ip3qf0us73brpjug-a.singapore-postgres.render.com/cybersquad'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

API_KEY = 'AIzaSyDYZbw_k1sDSg4CHgGP_1IK0iuIf8v9Ndo'
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

CORS(app)

@app.route('/balanceinfo', methods=['POST'])
def balancecheck():
    data = request.json
    email = data['email']
    amountleft = 0
    amountspent = 0
    amountsave = 0
    amountearn = 0
    
    try:
        with db.engine.connect() as connection:
            # For Amount Save
            query = text("SELECT amtsave FROM users WHERE email = :email")
            result = connection.execute(query, {"email": email})
            row = result.fetchone()
            amountsave = row[0] if row else 0
            # For Amount Spent
            current_date = dt.date.today()
            month = current_date.month
            year = current_date.year
            
            query = text("SELECT amount FROM monthamt WHERE email = :email AND monthno = :month AND year = :year")
            result = connection.execute(query, {"email": email, "month": month, "year": year})
            for row in result:
                amountspent += row[0]
            

            query = text("SELECT amount, amounttype FROM fixedexpense WHERE email = :email")
            result = connection.execute(query, {"email": email})
            for row in result:
                if row[1] == "outflow":
                    amountspent += row[0]
                else:
                    amountearn += row[0]


        # For Amount Left
        amountleft = amountearn - amountspent
        
        return jsonify({
            'amountleft': amountleft,
            'amountsave': amountsave,
            'amountspent': amountspent
        }), 200
        
    except Exception as e:
        return jsonify({'Message': str(e)}), 404
    
@app.route('/addspend', methods=['POST'])
def addspend():
    data = request.json
    email = data['email']
    expensename = data['expensename']
    expensetype = data['expensetype']
    amt = int(data['amount'])
    current_date = dt.date.today()
    month = current_date.month
    year = current_date.year
    dateofadd = current_date.strftime('%Y-%m-%d')

    try:
        with db.engine.connect() as connection:
            # Adding to allexpense
            query = text("INSERT INTO allexpense VALUES (:email, :dateofadd, :expensename, :expensetype, :amt)")
            connection.execute(query, {
                "email": email,
                "dateofadd": dateofadd,
                "expensename": expensename,
                "expensetype": expensetype,
                "amt": amt
            })

            # Adding to monthexpense
            query = text("SELECT amount FROM monthamt WHERE email = :email AND amounttype = :expensetype AND monthno = :month AND year = :year")
            result = connection.execute(query, {
                "email": email,
                "expensetype": expensetype,
                "month": month,
                "year": year
            }).fetchone()

            if result:
                new_amount = result[0] + amt
                query = text("UPDATE monthamt SET amount = :new_amount WHERE email = :email AND amounttype = :expensetype AND year = :year AND monthno = :month")
                connection.execute(query, {
                    "new_amount": new_amount,
                    "email": email,
                    "expensetype": expensetype,
                    "year": year,
                    "month": month
                })
            else:
                query = text("INSERT INTO monthamt VALUES (:email, :month, :year, :expensetype, :amt)")
                connection.execute(query, {
                    "email": email,
                    "month": month,
                    "year": year,
                    "expensetype": expensetype,
                    "amt": amt
                })

            connection.commit()

        return jsonify({'message': 'User updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/addfixed', methods=['POST'])
def addfixed():
    data = request.json
    email = data['email']
    expensename = data['expensename']
    amt = int(data['amount'])
    expensetype = data['amounttype']
    query = text("INSERT INTO fixedexpense VALUES (%s, %s, %s, %s)")
    # Execute the query using SQLAlchemy's connection
    with db.engine.connect() as conn:
        conn.execute(query, (email, expensename, amt, expensetype))
    
    return jsonify({'message': 'User updated successfully'}), 200


@app.route('/influxlist',methods=['GET'])
def influxlist():
    query = text("Select amountname,amount from fixedexpense where amounttype='inflow'")
    with db.engine.connect() as connection:
        object = connection.execute(query).fetchall()
    return jsonify({'Values':object})

@app.route('/addinflux',methods=['POST'])
def addinflux():
    data = request.json
    query = text("Insert into fixedexpense values(:email,:earnname,:amt,'inflow')")
    earnname = data['earningname']
    amt = data['earningamt']
    email = data['email']
    with db.engine.connect() as connection:
        connection.execute(query,{
            "email":email,
            "earnname":earnname,
            "amt":amt
        })
    return jsonify({'Message':'Earning Added Successfully'})


@app.route('/latestspend',methods=['POST'])
def latestspend():
    data=request.json
    email=data['email']
    query = 'SELECT expensename,expensetype,expenseamount,dateofadd FROM allexpense where email=:email ORDER BY dateofadd DESC LIMIT 5;'
    result = []
    with db.engine.connect() as connection:
        result = connection.execute(query,{
            "email":email
        }).fetchall()
        return jsonify({'spendlist':result})

@app.route('/bargraph',methods=['POST'])
def bargraph():
    body = request.json
    email=body['email']
    current_date = dt.date.today()
    month = current_date.month
    year = current_date.year
    casual = []
    unexpected =[]
    variable = []
    months = []
    recurring = 0
    with db.engine.connect() as connection:
        for i in range(3,-1,-1):
            query = text("Select amounttype,amount from monthamt where email=:email and monthno=:month and year=:year")
            if(month-i<=0):
                year-=1
                month=12-(month-i)
                months.append(month)
            else:
                months.append(month-i)
            result = connection.execute(query,{
                "email":email,
                "month":month-i,
                "year":year
            }).fetchall()

            for j in result:
                if j[0]=="unexpected":
                    unexpected.append(j[1])
                elif j[0]=="variable":
                    variable.append(j[1])
                else:   
                    casual.append(j[1])

        
        query = text("Select amount,amounttype from fixedexpense where email=:email")
        result = connection.execute(query,{
            "email":email
        }).fetchall()
        for i in result:
            if i[1]!="inflow":
                recurring+=i[0]
    return jsonify({'casual':casual,'unexpected':unexpected,'variable':variable,'recurring':recurring,'months':months})


@app.route('/loanlist',methods=['POST'])
def loanlist():
    body = request.json
    email = body['email']
    result = []
    with db.engine.connect() as connection:
        query = text("Select * from loan where email=:email")
        result = connection.execute(query,{
            "email":email
        }).fetchall()
    return jsonify({'loanlist':result})


@app.route('/addloan',methods=['POST'])
def addloan():
    try:
        body = request.json
        email = body['email']
        loanname = body['loanname']
        loanamt = body['loanamt']
        loanint = body['loanint']
        loantime = body['loantime']
        with db.engine.connect() as connection:
            advice = descriploan(email,loanname,loanamt,loanint,loantime)
            query = text("insert into loan values (:email,:loanname,:loanamt,:loanint,:loantime,:advice)")
            connection.execute(query,{
                "email":email,
                "loanname":loanname,
                "loanamt":loanamt,
                "loanint":loanint,
                "loantime":loantime,
                "advice":advice
            })
            return jsonify({'Message':'Successs'}),200
    except:
        return jsonify({'Message':'Error has occured'}),404
    

def descriploan(email,loanname,loanamt,loanint,loantime):

    earning = 0
    query = text("select amount,amounttype from fixedexpense where email=:email")
    with db.engine.connect() as connection:
        result = connection.execute(query,{
            "email":email
        }).fetchall()
        for i in result:
            earning += i[1] == 'inflow' and i[0] or -i[0]
        
        query = text("Give a html insertable text on step approach as on how someone earning :earning can finish a loan having the loan amount as :loanamt , loan interest as :loanint and loan time as :loantime in india and if it is not possible mention the same, please take the money to be in rupees and give code that can be used in html directly and dont mention html anywhere")
        connection.execute(query,{
            "earning":earning,
            "loanamt":loanamt,
            "loanint":loanint,
            "loantime":loantime
        })
        response = model.generate_content(query)
        advice = response.text
        cleaned = re.sub(r'```|html', '', advice)
        return cleaned

if __name__ == '__main__':
    app.run(debug=True)