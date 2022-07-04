# gnumake-tokenpool/js

javascript jobclient and jobserver for the GNU make tokenpool protocol

## install

```
npm install git+https://github.com/milahu/gnumake-tokenpool
```

## usage

```js
import { JobClient } from 'gnumake-tokenpool';

const jobClient = JobClient();

const token = jobClient.acquire();

// do some work

jobClient.release(token);
```

see also [test/jobclient/test.mjs](test/jobclient/test.mjs)

## details

for implementation details, see [details.md](details.md)
