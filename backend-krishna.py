from flask import Flask, request,jsonify
from flask_cors import CORS
from flask_mysqldb import MySQL
import datetime as dt
import google.generativeai as genai
import re


app = Flask(__name__)
mysql = MySQL(app)
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'keerkrish'
app.config['MYSQL_DB'] = 'cybersquad'

API_KEY = 'AIzaSyDYZbw_k1sDSg4CHgGP_1IK0iuIf8v9Ndo'
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

CORS(app)

@app.route('/hello',methods=['POST'])
def function1():
    data = request.json
    name = data.get('name','world')
    age = data.get('age',00)
    return jsonify(name=name,age=age)

@app.route('/balanceinfo',methods=['POST'])
def balancecheck():
    data = request.json
    email= data['email']
    amountleft = 0
    amountspent = 0
    amountsave = 0
    amountearn = 0
    try:
        #For Amount Save
        cur = mysql.connection.cursor()
        query = "Select amtsave from users where email=%s"
        cur.execute(query,(email,))
        mysql.connection.commit()
        result = cur.fetchone()
        amountsave = result[0]
        #For Amount Spent
        current_date = dt.date.today()
        month = current_date.month
        year = current_date.year
        query = "select amount from monthamt where email=%s and monthno=%s and year=%s"
        cur.execute(query,(email,month,year))
        mysql.connection.commit()
        result = cur.fetchall()
        for i in result:
            amountspent+=i[0]
        query = "select amount,amounttype from fixedexpense where email=%s"
        cur.execute(query,(email,))
        mysql.connection.commit()
        result = cur.fetchall()
        for i in result:
            if(i[1]=="outflow"):
                amountspent+=i[0]
            else:
                amountearn+=i[0]
        #For Amount Left
        amountleft = amountearn - amountspent
        return jsonify({'amountleft':amountleft,'amountsave':amountsave,'amountspent':amountspent}),200
    except Exception as e:
        return jsonify({'Message':f"{e}"}),404

@app.route('/test',methods=['GET'])
def test():
    cur = mysql.connection.cursor()
    query = "Select * from monthamt"
    cur.execute(query)
    mysql.connection.commit()
    result = cur.fetchall()
    print(result)
    cur.close()
    return jsonify({'Message':'Works'}),200


#This function is to add new expenses to the total monthly expense and also list of Expense
@app.route('/addspend',methods=['POST'])
def addspend():
    data = request.json
    cur = mysql.connection.cursor()
    email = data['email']
    expensename = data['expensename']
    expensetype = data['expensetype']

    amt = int(data['amount'])
    current_date = dt.date.today()
    month = current_date.month
    year = current_date.year
    dateofadd = current_date.strftime('%Y-%m-%d')
    #Adding to allexpense
    cur.execute("INSERT INTO allexpense VALUES (%s,%s,%s,%s,%s)", (email,dateofadd,expensename,expensetype,amt))
    mysql.connection.commit()
    #Adding to monthexpense
    query = "Select * from monthamt where email=%s and amounttype=%s and monthno=%s and year=%s"
    cur.execute(query,(email,expensetype,month,year))
    result = cur.fetchone()
    if result:
        result = result[4]+amt
        query = "update monthamt set amount=%s where email=%s and amounttype=%s and year=%s and monthno=%s"
        cur.execute(query,(result,email,expensetype,year,month))
        mysql.connection.commit()
    else:
        query = "insert into monthamt values (%s,%s,%s,%s,%s)"
        cur.execute(query,(email,month,year,expensetype,amt))
        mysql.connection.commit()
    cur.close()
    return jsonify({'message':'User updated successfully'}),200

@app.route('/addfixed',methods=['POST'])
def addfixed():
    data = request.json
    email = data['email']
    expensename = data['expensename']
    amt = int(data['amount'])
    expensetype = data['amounttype']
    cur = mysql.connection.cursor()
    query = "Insert into fixedexpense values (%s,%s,%s,%s)"
    cur.execute(query,(email,expensename,amt,expensetype,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'message':'User updated successfully'}),200
    
@app.route('/influxlist',methods=['GET'])
def influxlist():
    query = "Select amountname,amount from fixedexpense where amounttype='inflow'"
    cur = mysql.connection.cursor()
    cur.execute(query)
    mysql.connection.commit()
    object = cur.fetchall()
    cur.close()
    return jsonify({'Values':object})

@app.route('/addinflux',methods=['POST'])
def addinflux():
    data = request.json
    query = "Insert into fixedexpense values(%s,%s,%s,%s)"
    earnname = data['earningname']
    amt = data['earningamt']
    email = data['email']
    cur=mysql.connection.cursor()
    cur.execute(query,(email,earnname,amt,'inflow'))
    mysql.connection.commit()
    cur.close()
    return jsonify({'Message':'Earning Added Successfully'})
    

@app.route('/latestspend',methods=['POST'])
def latestspend():
    data=request.json
    email=data['email']
    cur = mysql.connection.cursor()
    query = 'SELECT expensename,expensetype,expenseamount,dateofadd FROM allexpense where email=%s ORDER BY dateofadd DESC LIMIT 5;'
    cur.execute(query,(email,))
    mysql.connection.commit()
    result = cur.fetchall()
    cur.close()
    return jsonify({'spendlist':result})

@app.route('/bargraph',methods=['POST'])
def bargraph():
    body = request.json
    email=body['email']
    cur = mysql.connection.cursor()
    current_date = dt.date.today()
    month = current_date.month
    year = current_date.year
    casual = []
    unexpected =[]
    variable = []
    months = []
    recurring = 0
    for i in range(3,-1,-1):
        query = 'Select amounttype,amount from monthamt where email=%s and monthno=%s and year=%s'
        if(month-i<=0):
            year-=1
            month=12-(month-i)
            months.append(month)
        else:
            months.append(month-i)
        cur.execute(query,(email,month-i,year))
        mysql.connection.commit()
        result = cur.fetchall()
        print("result=",result)
        for j in result:
            if j[0]=="unexpected":
                unexpected.append(j[1])
            elif j[0]=="variable":
                variable.append(j[1])
            else:   
                casual.append(j[1])
    query = "Select amount,amounttype from fixedexpense where email=%s"
    cur.execute(query,(email,))
    mysql.connection.commit()
    result = cur.fetchall()
    for i in result:
        if i[1]!="inflow":
            recurring+=i[0]
    return jsonify({'casual':casual,'unexpected':unexpected,'variable':variable,'recurring':recurring,'months':months})

@app.route('/loanlist',methods=['POST'])
def loanlist():
    body = request.json
    email = body['email']
    cur = mysql.connection.cursor()
    query = 'Select * from loan where email=%s'
    cur.execute(query,(email,))
    mysql.connection.commit()
    result = cur.fetchall()
    cur.close()
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
        cur = mysql.connection.cursor()
        advice = descriploan(email,loanname,loanamt,loanint,loantime)
        query = 'insert into loan values (%s,%s,%s,%s,%s,%s)'
        cur.execute(query,(email,loanname,loanamt,loanint,loantime,advice))
        mysql.connection.commit()
        cur.close()
        return jsonify({'Message':'Successs'}),200
    except:
        return jsonify({'Message':'Error has occured'}),404
    
def descriploan(email,loanname,loanamt,loanint,loantime):
    cur = mysql.connection.cursor()
    earning = 0
    query = 'select amount,amounttype from fixedexpense where email=%s'
    cur.execute(query,(email,))
    mysql.connection.commit()
    result = cur.fetchall()
    for i in result:
        earning += i[1] == 'inflow' and i[0] or -i[0]
    query = f"Give a html insertable text on step approach as on how someone earning {earning} can finish a loan having the loan amount as {loanamt} , loan interest as {loanint} and loan time as {loantime} in india and if it is not possible mention the same, please take the money to be in rupees and give code that can be used in html directly and dont mention html anywhere"
    response = model.generate_content(query)
    advice = response.text
    cleaned = re.sub(r'```|html', '', advice)
    return cleaned








if __name__ == '__main__':
    app.run(debug=True)