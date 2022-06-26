//import { JobClient } from '@milahu/gnumake-jobclient';
import { JobClient } from '../JobClient.js';

//import process from 'process';

//const sleep = ms => new Promise(r => setTimeout(r, ms));

//console.log(`test: ${process.argv.slice(2).join(' ')}`);

const jobClient = JobClient();

if (!jobClient) {
  console.log(`test: jobClient init failed`);
}
else {
  console.log(`test: jobClient init ok`);

  console.log(`test: jobClient maxJobs = ${jobClient.maxJobs()}`);
  console.log(`test: jobClient maxLoad = ${jobClient.maxLoad()}`);

  const tokenList = [];

  // NOTE n-1 error: dont acquire token for the first worker
  // only acquire tokens if we need 2 or more workers (parallelism)
  // assumption: the worker-scheduler produces zero cpu load
  for (let i = 0; i < jobClient.maxJobs(); i++) {
    let token;
    try {
      token = jobClient.acquire();
    }
    catch (e) {
      console.log(`test: failed to acquire token: ${e}`);
      break;
    }
    if (token == null) {
      console.log(`test: failed to acquire token: jobserver is full`);
      break;
    }
    tokenList.push(token);
    console.log(`test: acquired token ${token}. tokenList.length = ${tokenList.length}. jobClient.numTokens() = ${jobClient.numTokens()}`);
    //await sleep(100);
  }

  // all tokens acquired
  // try one more -> should fail
  let token;
  try {
    token = jobClient.acquire();
    if (token == null) {
      console.log(`test: ok: jobserver is full`);
    }
    else {
      console.log(`test: error: acquired token ${token}. tokenList.length = ${tokenList.length}. jobClient.numTokens() = ${jobClient.numTokens()}`);
    }
  }
  catch (e) {
    console.log(`test: failed to acquire token: ${e}`);
  }

  while (tokenList.length > 0) {
    const token = tokenList.pop();
    jobClient.release(token);
    console.log(`test: released token ${token}. tokenList.length = ${tokenList.length}. jobClient.numTokens() = ${jobClient.numTokens()}`);
    //await sleep(100);
  }
}
console.log('');
