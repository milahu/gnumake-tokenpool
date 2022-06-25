# gnumake-jobclient-js

javascript client for the GNU make jobserver

## install

```
npm install @milahu/gnumake-jobclient
```

## usage

```js
import { Jobclient } from '@milahu/gnumake-jobclient';

const jobclient = await Jobclient();

const token = await jobclient.acquire();

// do some work

await jobclient.release(token);
```

see also [test/test.mjs](test/test.mjs)
