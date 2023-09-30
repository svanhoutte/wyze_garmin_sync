import os
import sys
import garth
from getpass import getpass

if len(sys.argv) < 2:
    print("Use %s <file name>" % sys.argv[0])
    exit()

if not os.path.isfile(sys.argv[1]):
    print("File %s not found" % sys.argv[1])
    exit()

tokens_dir = './tokens'

email = os.environ['Garmin_username']
password = os.environ['Garmin_password']

try:
    garth.resume(tokens_dir)
    garth.client.username
except:
    try:
        garth.login(email, password)
        garth.save(tokens_dir)
    except:
        email = input("Enter email address: ")
        password = getpass("Enter password: ")
        try:
            garth.login(email, password)
            garth.save(tokens_dir)
        except Exception as exc:
            print(repr(exc))
            exit()

with open(sys.argv[1], "rb") as f:
    garth.client.upload(f)
