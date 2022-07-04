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

problem: closeTimer is never called, program hangs after `read ...`

```js
const fs = require("fs");
//const process = require("process");
//const fdRead = parseInt(process.argv[1]);
const fdRead = 0; // stdin
const buf = Buffer.alloc(1);

//var fdReadDup = os.dup(fdNum); // not implemented in node
var fdReadDup = fs.openSync(`/proc/self/fd/${fdRead}`); // os.dup on linux
var closeTimer = setTimeout(() => {
  console.error("timeout");
  fdReadDup.close();
}, 1000);
try {
  console.error(`read ...`);
  fs.readSync(fdReadDup, buf);
  clearTimeout(closeTimer);
  console.error(`read done`);
  const token = buffer.readInt8();
  console.log(`acquired token ${token}`);
} catch (e) {
  clearTimeout(closeTimer);
  if (e.errno == -11) {
    console.log("jobserver is full");
  }
  else {
    console.error(`error ${e}`);
  }
}
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

## memory usage

aka resident set size (RSS)

```sh
$(which time) -v dd bs=1 count=1 status=none
# Maximum resident set size (kbytes): 3780

$(which time) -v sh -c 'read -n1 -t0.1'
# Maximum resident set size (kbytes): 3920

printf + | $(which time) -v node -e '
  var fs = require("fs");
  var process = require("process");
  var buf = Buffer.alloc(1);
  try {
    fs.readSync(parseInt(process.argv[1]), buf);
    console.log(buf.readInt8());
  } catch (e) {}
' 0
# Maximum resident set size (kbytes): 40376
```
