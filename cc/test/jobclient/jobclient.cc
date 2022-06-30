// based on tokenpool_test.cc

#include "tokenpool.h"

#ifdef _WIN32
  #include <windows.h>
  #include <ctype.h>
#else
  #include <fcntl.h>
  #include <unistd.h>
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <cassert> // assert
#include <vector>

int main() {
  printf("init\n");
  bool ignore_jobserver = false;
  bool verbose_jobclient = true;
  double load_avg_ = 0.0;

  TokenPool* tokenpool_;

  if ((tokenpool_ = TokenPool::Get()) == NULL) {
    printf("TokenPool::Get failed\n");
    return 1;
  }
  printf("TokenPool::Get ok\n");

  if (!tokenpool_->SetupClient(ignore_jobserver, verbose_jobclient, load_avg_)) {
    delete tokenpool_;
    tokenpool_ = NULL;
    printf("tokenpool_->SetupClient failed. jobserver off? run make like 'make -j4'\n");
    return 1;
  }
  printf("tokenpool_->SetupClient ok\n");

  int token_id;

  // high-level interface: Acquire, Reserve, Release, Clear
  // with 'make -j10' this acquires 10 tokens
  printf("high-level interface\n");
  for (token_id = 0; token_id < 10; token_id++) {
    if (!tokenpool_->Acquire()) {
      printf("token %i: tokenpool_->Acquire failed\n", token_id);
      break;
    }
    tokenpool_->Reserve();
    printf("token %i: tokenpool_->Acquire ok\n", token_id);
  }
  printf("acquired %i tokens\n", token_id);

  // release all tokens. same as: tokenpool_->Clear();
  printf("releasing %i tokens\n", token_id);
  for (; token_id > 0; token_id--) {
    printf("token %i: tokenpool_->Release\n", token_id);
    tokenpool_->Release();
  }

  // low-level interface: AcquireToken, ReleaseToken
  // with 'make -j10' this acquires 9 tokens
  printf("low-level interface\n");
  size_t worker_count = 1;
  size_t job_count = 4; // == max_worker_count
  std::vector<int> tokens_;
  int token;
  while (worker_count < job_count) {
    if ((token = tokenpool_->AcquireToken()) < 0) {
      printf("token %i: tokenpool_->AcquireToken failed. jobserver is full\n", token_id);
      break;
    }
    printf("token %i: tokenpool_->AcquireToken ok: token = %i\n", token_id, token);
    tokens_.push_back(token);
    worker_count++;
  }
  printf("acquired %li tokens -> worker_count = %li\n", tokens_.size(), worker_count);

  // release all tokens. same as: tokenpool_->Clear();
  printf("releasing %li tokens\n", tokens_.size());
  while (tokens_.size() > 0) {
    token = tokens_.back();
    printf("tokenpool_->ReleaseToken %i\n", token);
    tokenpool_->ReleaseToken(token);
    tokens_.pop_back();
  }
  printf("released all tokens\n");

  // cleanup
  delete tokenpool_;
  tokenpool_ = NULL;

  return 0;
}
