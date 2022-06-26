//import { JobClient } from '@milahu/gnumake-jobclient';
import { JobClient } from '../JobClient.js';

//import process from 'process';

//const sleep = ms => new Promise(r => setTimeout(r, ms));

//console.log(`test: ${process.argv.slice(2).join(' ')}`);

const jobclient = JobClient();

if (!jobclient) {
  console.log(`test: jobclient init failed`);
}
else {
  console.log(`test: jobclient init ok`);

  console.log(`test: jobclient maxJobs = ${jobclient.maxJobs()}`);
  console.log(`test: jobclient maxLoad = ${jobclient.maxLoad()}`);

  const tokenList = [];

  for (let i = 0; i < jobclient.maxJobs(); i++) {
    let token;
    try {
      token = jobclient.acquire();
    }
    catch (e) {
      console.log(`test: failed to acquire token: ${e}`);
      break;
    }
    tokenList.push(token);
    console.log(`test: acquired token ${token}. tokenList.length = ${tokenList.length}`);
    //await sleep(100);
  }

  // all tokens acquired
  // try one more -> should fail
  let token;
  try {
    token = jobclient.acquire();
    console.log(`test: error: acquired token ${token}. tokenList.length = ${tokenList.length}`);
  }
  catch (e) {
    if (e.errno == -11) {
      console.log(`test: acquired all tokens`);
    }
    else {
      throw e;
    }
  }

  while (tokenList.length > 0) {
    const token = tokenList.pop();
    jobclient.release(token);
    console.log(`test: released token ${token}. tokenList.length = ${tokenList.length}`);
    //await sleep(100);
  }
}
console.log('');
