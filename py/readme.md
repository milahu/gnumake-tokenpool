# gnumake-jobclient-py

python client for the GNU make jobserver

## install

```
pip install git+https://github.com/milahu/gnumake-jobclient-py
```

## usage

```py
import gnumake_jobclient

jobClient = gnumake_jobclient.JobClient()

token = jobClient.acquire()

# do some work

jobClient.release(token)
```

see also [test/jobclient/test.py](test/jobclient/test.py)

## similar projects

* https://github.com/olsner/jobclient
* https://github.com/milahu/gnumake-jobclient-js

## related

* [GNU make jobserver implementation](http://make.mad-scientist.net/papers/jobserver-implementation/)
* [ninja with jobclient and jobserver](https://gitlab.kitware.com/cmake/cmake/-/issues/21597)
