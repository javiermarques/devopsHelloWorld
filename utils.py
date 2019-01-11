import psycopg2
def parseStackOutput(r):
    stack, = r['Stacks']
    outputs = stack['Outputs']

    out = {}
    for o in outputs:
        key = o['OutputKey']
        out[key] = o['OutputValue']

    return out

def initDatabase(host, user, psw, appPsw, env):
    conn = psycopg2.connect(host=host, database="postgres", user=user, password=psw)
    conn.set_session(autocommit=True)
    cursor = conn.cursor()

    cursor.execute("create user app with encrypted password '" + appPsw + "';")
    # cursor.execute("create database \"HelloWorldApp\";")
    cursor.execute("grant all privileges on database \"HelloWorldApp" + env + "\" to app;")

    conn.commit()

    cursor.close()
    conn.close()
