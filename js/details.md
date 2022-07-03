# details

implementation details

aka: what did not work

## acquire

wanted: fs.readSync with timeout

* [How to timeout an fs.read in node.js? at stackoverflow.com](https://stackoverflow.com/questions/20808126/how-to-timeout-an-fs-read-in-node-js)

### fs.readSync

```js
const buffer = Buffer.alloc(1);
try {
  bytesRead = fs.readSync(fdRead, buffer);
}
catch (e) {
  if (e.errno == -11) {
    return null; // jobserver is full, try again later
  }
  throw e;
}
const token = buffer.readInt8();
```

problem: read can block until token becomes available

example: read is blocking for 20 seconds

```
debug node.py 33755 2022-07-03 16:25:14.824:   jobclient.js 33777 2022-07-03 16:25:14.824: acquire: read ...
debug node.py 33755 2022-07-03 16:25:34.328:   jobclient.js 33777 2022-07-03 16:25:34.327: acquire: read done: 1 bytes
```

### os.dup and fs.readSync

problem: [os.dup is not implemented in node](https://github.com/nodejs/node/issues/41733)

`dup` works in c, c++, python

```js
fdReadDup = os.dup(fdRead); // WONTFIX os.dup is not implemented in node

const closeTimer = setTimeout(() => {
  fdReadDup.close();
}, 100);

const buffer = Buffer.alloc(1);
try {
  bytesRead = fs.readSync(fdReadDup, buffer);
  clearTimeout(closeTimer);
}
catch (e) {
  clearTimeout(closeTimer);
  if (e.errno == -11) {
    return null; // jobserver is full, try again later
  }
  throw e;
}
const token = buffer.readInt8();
```

### write invalid token

write invalid token to the pipe to unblock readSync

WONTFIX race condition. other process can read the invalid token between writeSync and readSync

WONTFIX other jobclients should ignore invalid tokens, but we cant tell other jobclients what to do

```js
const closeTimer = setTimeout(() => {
  const buffer = Buffer.alloc(1); // buffer.readInt8() == 0
  fs.writeSync(fdWrite, buffer);
}, 100);

const buffer = Buffer.alloc(1);
try {
  bytesRead = fs.readSync(fdReadDup, buffer);
  clearTimeout(closeTimer);
}
catch (e) {
  clearTimeout(closeTimer);
  if (e.errno == -11) {
    return null; // jobserver is full, try again later
  }
  throw e;
}
const token = buffer.readInt8();
```
