import sys
import gnumake_tokenpool

try:
  jobClient = gnumake_tokenpool.JobClient()
except gnumake_tokenpool.NoJobServer:
  print(f"test: jobClient init failed")
  sys.exit(0)

print()
print(f"test: jobClient init ok")
print(f"test: jobClient maxJobs = {jobClient.maxJobs}")
print(f"test: jobClient maxLoad = {jobClient.maxLoad}")

tokenList = []

# NOTE n-1 error: dont acquire token for the first worker
# only acquire tokens if we need 2 or more workers (parallelism)
# assumption: the worker-scheduler produces zero cpu load

print()
print(f"test: acquire {(jobClient.maxJobs - 1)} tokens ...")

for i in range(0, (jobClient.maxJobs - 1)):
  token = None
  print()
  print(f"test: acquire token {(i + 1)} of {(jobClient.maxJobs - 1)}")
  try:
    token = jobClient.acquire()
  except Exception as e:
    print(f"error: {e}")
    break
  if token == None:
    print(f"done: jobserver is full")
    break
  tokenList.append(token)
  print(f"ok: got token {token}. len(tokenList) = {len(tokenList)}")

# all tokens acquired
# try one more -> should fail
print()
print(f"test: acquire excess token ...")
token = None
try:
  token = jobClient.acquire()
  if token == None:
    print(f"test: acquire excess token failed = ok")
  else:
    print(f"test: acquire excess token ok (token {token}) = fail")
except Exception as e:
  print(f"test: acquire excess token error {e}")

print()
print(f"test: release {len(tokenList)} tokens ...")
while len(tokenList) > 0:
  token = tokenList.pop()
  jobClient.release(token)
