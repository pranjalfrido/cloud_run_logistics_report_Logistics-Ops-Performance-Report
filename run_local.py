"""
Local runner: sends report for 30 Sep 2026, only to pranjal.t@myfrido.com.
  today  = 2026-09-30
  cutoff = 2026-09-15  (30 - 15 days)
  start  = 2026-08-16  (cutoff - 30 days)
"""
import sys, os, pathlib, tempfile, subprocess, yaml

base = pathlib.Path(__file__).parent

# Load env vars from env.yaml
with open(base / 'env.yaml', encoding='utf-8') as f:
    env_vars = yaml.safe_load(f)
for k, v in env_vars.items():
    os.environ.setdefault(k, str(v))

src = base / 'main.py'
code = src.read_text(encoding='utf-8')

# 1. Fix the date: replace date.today() with a fixed date
code = code.replace(
    "today      = date.today()",
    "today      = date(2026, 9, 30)"
)

# 2. Override recipients — only pranjal.t@myfrido.com, no CC
code = code.replace(
    "TO_EMAILS     = os.environ.get('EMAIL_TO', 'arif@myfrido.com,sachin.s@myfrido.com,amit.n@myfrido.com,sachin.m@myfrido.com,pranjal.t@myfrido.com,yash.p@myfrido.com').split(',')",
    "TO_EMAILS     = ['pranjal.t@myfrido.com']"
)
code = code.replace(
    "CC_EMAILS     = os.environ.get('EMAIL_CC', 'mukesh.c@myfrido.com,abhishek.v@myfrido.com,ravindra.d@myfrido.com,saivarun.g@myfrido.com,akash.d@myfrido.com,sourav.b@myfrido.com,abhay.p@myfrido.com,atharva.s@myfrido.com,nikhil.k@myfrido.com,ashikesh.n@myfrido.com,yash.s@myfrido.com,suraj.s@myfrido.com,hemant.k@myfrido.com,tushar.g@myfrido.com,Rahul.m@myfrido.com,farukh.m@myfrido.com,Krishna.kadam@myfrido.com,ranjit.j@myfrido.com,sagar.k@myfrido.com,Syed.h@myfrido.com').split(',')",
    "CC_EMAILS     = []"
)

# 3. Fix ccRecipients to skip empty list safely
code = code.replace(
    "'ccRecipients':  [{'emailAddress': {'address': e.strip()}} for e in CC_EMAILS],",
    "'ccRecipients':  [{'emailAddress': {'address': e.strip()}} for e in CC_EMAILS if e.strip()],"
)

# Write to a temp file and run it
with tempfile.NamedTemporaryFile(
    mode='w', suffix='_local_run.py', encoding='utf-8',
    dir=pathlib.Path(__file__).parent, delete=False
) as f:
    f.write(code)
    tmp_path = f.name

try:
    result = subprocess.run(
        [sys.executable, tmp_path],
        cwd=str(base),
        env=os.environ.copy()
    )
    sys.exit(result.returncode)
finally:
    os.unlink(tmp_path)
