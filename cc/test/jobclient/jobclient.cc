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

int main() {
  printf("init\n");
  bool ignore_jobserver = false;
  double load_avg_ = 0.0;

  TokenPool* tokens_;

  if ((tokens_ = TokenPool::Get()) == NULL) {
    printf("TokenPool::Get failed\n");
    return 1;
  }
  printf("TokenPool::Get ok\n");

  if (!tokens_->SetupClient(
    ignore_jobserver,
    true, // verbose
    load_avg_
  )) {
    delete tokens_;
    tokens_ = NULL;
    printf("tokens_->SetupClient failed. jobserver off? run make like 'make -j4'\n");
    return 1;
  }
  printf("tokens_->SetupClient ok\n");

  int token_id;
  for (token_id = 0; token_id < 10; token_id++) {
    if (!tokens_->Acquire()) {
      printf("token %i: tokens_->Acquire failed\n", token_id);
      break;
    }
    tokens_->Reserve();
    printf("token %i: tokens_->Acquire ok\n", token_id);
  }
  printf("acquired %i tokens\n", token_id);

  // release all tokens. same as: tokens_->Clear();
  printf("releasing %i tokens\n", token_id);
  for (; token_id > 0; token_id--) {
    printf("token %i: tokens_->Release\n", token_id);
    tokens_->Release();
  }

  return 0;
}
