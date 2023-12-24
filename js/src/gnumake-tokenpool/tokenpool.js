// jobclient for the gnumake jobserver

// based on https://github.com/olsner/jobClient/blob/master/jobClient.h
// license: MIT
// copyright: (c) 2022 Milan Hauth <milahu@gmail.com>

// NOTE n-1 error
// make counts this jobclient as one job
// so we dont need a token for the first worker (serial processing).
// we only need tokens for 2 or more workers (parallel processing).

// NOTE maxJobs
// maxJobs is the global limit for all make jobs,
// so this jobclient can get less than (maxJobs-1) tokens.
// to find the maximum number of free tokens,
// you must acquire them all.

// NOTE debug logging
// callers like "rollup --silent" will hide debug output

// TODO move code to jobclient.js

const process = require('process');
const fs = require('fs');
const os = require('os');
const child_process = require('child_process');



const debug = Boolean(process.env.DEBUG_JOBCLIENT);

const log = (msg) => console.error(`debug jobclient.js ${process.pid} ${new Date().toLocaleString('af')}.${String(Date.now() % 1000).padStart(3, '0')}: ${msg}`); // print to stderr

function parseFlags(makeFlags) {

  let fdRead, fdWrite, fifoPath, maxJobs, maxLoad;

  for (const flag of makeFlags.split(/\s+/)) {
    let match;
    if (
      (match = flag.match(/^--jobserver-(?:auth|fds)=(?:(\d+),(\d+)|fifo:(.*))$/))
    ) {
      if (match[1] && match[2]) {
        // make --jobserver-style=pipe
        fdRead = parseInt(match[1]);
        fdWrite = parseInt(match[2]);
      }
      else if (match[3]) {
        // make --jobserver-style=fifo
        fifoPath = match[3];
      }
    }
    else if (match = flag.match(/^-j(\d+)$/)) {
      maxJobs = parseInt(match[1]);
    }
    else if (match = flag.match(/^-l(\d+)$/)) {
      maxLoad = parseInt(match[1]);
    }
  }

  return { fdRead, fdWrite, fifoPath, maxJobs, maxLoad };
}



function validateToken(token) {

  if (token == null) {
    throw new Error('empty token');
  }

  if (typeof(token) != 'number' || token < 0 || 255 < token) {
    throw new Error('invalid token');
  }
}



/**
* read with timeout. unix only
*
* https://stackoverflow.com/questions/20808126/how-to-timeout-an-fs-read-in-node-js
*
* @param {number | string} fdOrPath
* @param {number} blockSize
* @param {number} timeout
*  param {child_process.SpawnOptions} options
* @param {Object} options
* @param {number} [options.numBlocks=1]
* @param {string=} options.encoding
*/
function readWithTimeoutDD(fdOrPath, blockSize, timeout, options = {}) {
  if (!options) options = {};
  const numBlocks = options.numBlocks || 1;
  if (options.numBlocks) delete options.numBlocks;
  if (options.timeout) throw Error('dont set options.timeout');
  const ddArgs = [`bs=${blockSize}`, `count=${numBlocks}`, 'status=none'];
  const stdio = [fdOrPath, 'pipe', 'pipe'];
  if (typeof fdOrPath == 'string') {
    if (!fs.existsSync(fdOrPath)) throw Error(`no such file: ${fdOrPath}`);
    ddArgs.push(`if=${fdOrPath}`);
    stdio[0] = null;
  }
  else if (typeof fdOrPath != 'number') {
    throw Error(`fdOrPath must be number or string`);
  }
  //console.dir({ fdOrPath, blockSize, timeout, stdio, ddArgs });
  const reader = child_process.spawnSync('dd', ddArgs, {
    timeout,
    stdio,
    windowsHide: true,
    ...options,
  });
  if (reader.error) throw reader.error;
  return reader.stdout;
}



/**
* read with timeout
* @param {number | string} fdOrPath
* @param {number} size
* @param {number} timeout
* @param {Object} options
* @param {number} [options.blockSize=4096]
* @param {string=} options.encoding
*/
function readWithTimeoutNode(fdOrPath, size, timeout, options = {}) {
  if (!options) options = {};
  if (typeof(fdOrPath) != 'number') {
    throw Error(`reading from path not implemented. fdOrPath must be number`);
  }
  if (typeof(size) != 'number') {
    throw Error(`invalid size: ${size}`);
  }
  size = size | 0; // enforce integer size
  if (size < 0) {
    // TODO "size == -1" means: read until EOF
    throw Error(`invalid size: ${size}`);
  }
  if (size == 0) {
    // for child_process.execSync the default encoding is "buffer"
    // https://nodejs.org/api/child_process.html#child_processexecsynccommand-options
    if (!options.encoding || options.encoding == 'buffer') {
      return Buffer.alloc(0);
    }
    // FIXME handle "unrecognized character encoding"
    // If encoding is 'buffer', or an unrecognized character encoding, Buffer objects will be passed to the callback instead.
    //if (is_unrecognized(options.encoding)) return Buffer.alloc(0);
    return '';
  }
  const blockSizeDefault = 4096; // TODO better? 64 * 1024?
  const blockSize = Math.min(size, (Number(options.blockSize) | 0) || blockSizeDefault);
  if (options.blockSize) delete options.blockSize;
  if (options.timeout) throw Error('dont set options.timeout, use the timeout parameter');
  const nodeCode = [
    "const {stdout} = require('process');",
    "const {readSync} = require('fs');",
    "const {Buffer} = require('buffer');",
    `const buf = Buffer.alloc(${blockSize});`,
    "let done = 0;",
    "const sleep = ms => new Promise(r => setTimeout(r, ms));",
    "async function main() {",
    `  while (done < ${size}) {`,
    `    const n = readSync(${fdOrPath}, buf, 0, ${blockSize}, -1);`,
    "    if (n > 0) stdout.write(buf);",
    "    done += n;",
    // reduce cpu time from 100% to 0%
    // 200ms is arbitrary, 50ms would be enough to reduce cpu time
    "    await sleep(200);",
    "  }",
    "}",
    "main();",
  ].join('\n');
  console.log('nodeCode:\n' + nodeCode); // debug
  const nodeExe = process.argv[0];
  const nodeArgs = ['-e', nodeCode];
  // connect fdOrPath to stdin of the subprocess
  const stdio = [fdOrPath, 'pipe', 'pipe'];
  //console.dir({ fdOrPath, size, timeout, stdio, nodeArgs });
  const reader = child_process.spawnSync(nodeExe, nodeArgs, {
    timeout,
    stdio,
    windowsHide: true,
    ...options,
  });
  if (reader.error) throw reader.error;
  return reader.stdout;
}



// jobClient factory
exports.JobClient = function JobClient() {

  debug && log("init");

  const makeFlags = process.env.MAKEFLAGS;
  if (!makeFlags) {
    debug && log(`init failed: MAKEFLAGS is empty`);
    return null;
  }
  debug && log(`init: MAKEFLAGS: ${makeFlags}`);

  const flags = parseFlags(makeFlags);

  const fdFifo = flags.fifoPath && fs.openSync(flags.fifoPath, 'a+');

  const fdRead = flags.fdRead || fdFifo;
  const fdWrite = flags.fdWrite || fdFifo;

  const { maxJobs, maxLoad } = flags;

  debug && log(`init: fdRead = ${fdRead}, fdWrite = ${fdWrite}, maxJobs = ${maxJobs}, maxLoad = ${maxLoad}`);

  if (fdRead == undefined) {
    debug && log(`init failed: fds missing in MAKEFLAGS`);
    return null;
  }

  if (maxJobs == 1) {
    debug && log(`init failed: maxJobs == 1`);
    return null;
  }

  const buffer = Buffer.alloc(1);

  // TODO switch: if the "dd" command is available, use readWithTimeoutDD
  // otherwise, fall back to readWithTimeoutNode

  const readWithTimeout = readWithTimeoutDD;

  const jobClient = {
    acquire: () => {
      let bytesRead = 0;
      debug && log(`acquire: read ...`);

      /*
      // test: empty pipe
      const testBuffer = Buffer.alloc(999);
      try {
        bytesRead = fs.readSync(fdRead, testBuffer);
        log(`acquire: done empty pipe. got ${bytesRead} tokens`);
      }
      catch (e) {
        if (e.errno != -11) { // e.errno == -11: pipe is empty
          log(`acquire: failed to empty pipe: e.errno ${e.errno}, e ${e}`);
        }
      }
      bytesRead = 0;
      */

      // readSync with timeout via spawnSync
      // similar: rpc-sync https://github.com/ForbesLindesay/sync-rpc
      try {
        const readLen = 1;
        const readTimeout = 100;
        const output = readWithTimeout(fdRead, readLen, readTimeout);
        if (output.length == 0) {
          debug && log(`acquire: read empty`);
          return null; // jobserver is full, try again later
        }
        const token = output.readInt8();
        debug && log(`acquire: token = ${token}`);
        return token;
      }
      catch (e) {
        if (e.errno == -110) {
          debug && log(`acquire: read timeout`);
          return null; // jobserver is full, try again later
        }
        else {
          debug && log(`acquire: read error: ${e}`);
          throw e; // unexpected error
        }
      }
    },
    release: (token=43) => { // default token: str(+) == int(43)
      debug && log(`release: token = ${token}`);
      validateToken(token);
      buffer.writeInt8(token);
      let bytesWritten = 0;
      debug && log(`release: write ...`);
      // TODO retry loop
      try {
        bytesWritten = fs.writeSync(fdWrite, buffer);
      }
      catch (e) {
        //if (e.errno == -11) return false; // TODO errno?
        throw e;
      }
      debug && log(`release: write done: ${bytesWritten} bytes`);
      if (bytesWritten != 1) throw new Error('write failed');
      return true; // success
    },
    close: () => {
      if (fdFifo) {
        fs.closeSync(fdFifo);
      }
    },
  };

  // add read-only properties
  Object.defineProperties(jobClient, {
    maxJobs: { value: maxJobs, enumerable: true },
    maxLoad: { value: maxLoad, enumerable: true },
  });

  // TODO check fds
  // examples:
  // MAKEFLAGS="--jobserver-auth=3,4 -l32"
  // ls -nlv /proc/self/fd/
  //
  // jobserver on:
  // lr-x------ 1 1000 100 64 Jun 27 14:29 3 -> pipe:[102600042]
  // l-wx------ 1 1000 100 64 Jun 27 14:29 4 -> pipe:[102600042]
  //
  // jobserver off:
  // lr-x------ 1 1000 100 64 Jun 27 14:29 3 -> /proc/2370722/fd
  //
  // conditions for jobserver on:
  // * maxJobs is undefined // no. this is a bug in ninja-tokenpool. gnumake always sets -j in MAKEFLAGS
  // * fds 3 and 4 are connected
  // * fd 3 is readable
  // * fd 4 is writable
  // * fds 3 and 4 are pipes
  // * fds 3 and 4 are pipes with the same ID (?)

  // TODO windows: named semaphore

  function checkAccess(s, check="r") {
    const { uid: u, gid: g } = os.userInfo();
    const m = s.mode;
    if (check == "r") {
      return (
        ((s.uid == u) && (m & fs.constants.S_IRUSR)) ||
        ((s.gid == g) && (m & fs.constants.S_IRGRP)) ||
        (m & fs.constants.S_IROTH)
      ) != 0;
    }
    if (check == "w") {
      return (
        ((s.uid == u) && (m & fs.constants.S_IWUSR)) ||
        ((s.gid == g) && (m & fs.constants.S_IWGRP)) ||
        (m & fs.constants.S_IWOTH)
      ) != 0;
    }
    throw Exception("check must be r or w");
  }

  debug && log(`init: test fdRead`);
  const statsRead = fs.fstatSync(fdRead);
  if (!statsRead.isFIFO()) {
    debug && log(`init failed: fd ${fdRead} is no pipe`);
    return null;
  }
  if(!checkAccess(statsRead, 'r')) {
    debug && log(`init failed: fd ${fdRead} is not readable`);
    return null;
  }

  debug && log(`init: test fdWrite`);
  const statsWrite = fs.fstatSync(fdWrite);
  if (!statsWrite.isFIFO()) {
    debug && log(`init failed: fd ${fdWrite} is no pipe`);
    return null;
  }
  if(!checkAccess(statsWrite, 'w')) {
    debug && log(`init failed: fd ${fdWrite} is not writable`);
    return null;
  }

  debug && log(`init: test acquire`);
  // test acquire + release
  let token = null;
  try {
    token = jobClient.acquire();
    if (token == null) {
      debug && log("init ok: jobserver is full");
      return jobClient; // ok
    }
  }
  catch (e) {
    if (e.errno == -22) {
      debug && log("init failed: jobserver off");
      return null; // jobserver off
    }
    throw e; // unexpected error
  }
  debug && log(`init: test release`);
  if (jobClient.release(token) == false) {
    // TODO?
    //return null;
    throw new Error('init failed: release failed');
  }
  debug && log("init ok");
  return jobClient; // ok
}
