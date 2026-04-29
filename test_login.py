import urllib.request
import urllib.parse
from http.cookiejar import CookieJar

cj = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

login_url = "https://jjc-webapp-1.onrender.com/login"
data = urllib.parse.urlencode({'username': 'admin', 'password': 'admin123'}).encode('utf-8')

# Login
opener.open(login_url, data)

# Fetch students
try:
    res = opener.open("https://jjc-webapp-1.onrender.com/students")
    print("STATUS:", res.getcode())
    print("No 500 error found. Length:", len(res.read()))
except urllib.error.HTTPError as e:
    print("STATUS:", e.code)
    print(e.read().decode('utf-8'))
